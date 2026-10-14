#!/usr/bin/env python3
"""Validate a local device registry and dispatch explicit argv commands.

Only `run` starts a device command. Registry management and previews never
contact hardware. Uses only Python's standard library.
"""

import argparse
from contextlib import contextmanager, nullcontext
import copy
import errno
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LEGACY_REGISTRY = Path(__file__).resolve().parents[1] / "devices.json"
PARAM = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TOKEN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
ARG_FIELDS = {"type", "description", "minimum", "maximum", "enum", "default"}


class RegistryError(ValueError):
    """A registry or command cannot be used safely and unambiguously."""


class RegistryConflict(RegistryError):
    """A caller edited an old snapshot, or another writer currently owns it."""


def default_registry():
    """User data lives outside directories managed by Skill installers."""
    configured = os.environ.get("WUWU_DEVICES_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".wuwu-intelligence" / "devices.json"


def select_registry(explicit=None, action="list"):
    if explicit is not None:
        return Path(explicit).expanduser().resolve(), False
    target = default_registry()
    if not os.environ.get("WUWU_DEVICES_FILE") and not target.exists() and LEGACY_REGISTRY.is_file():
        if action in ("init", "register", "update"):
            raise RegistryError("发现安装目录中的旧档案，请先运行 migrate；不会创建空档案遮蔽已有设备")
        if action != "migrate":
            return LEGACY_REGISTRY, True
    return target, False


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"JSON 字段重复: {key}")
        result[key] = value
    return result


def parse_json(text):
    def reject_constant(value):
        raise RegistryError(f"JSON 不支持 {value}")

    try:
        return json.loads(text, object_pairs_hook=_unique_object,
                          parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"JSON 第 {exc.lineno} 行第 {exc.colno} 列: {exc.msg}") from exc


def read_snapshot(path):
    try:
        raw = Path(path).read_bytes()
        return parse_json(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest(), raw
    except (OSError, UnicodeError) as exc:
        raise RegistryError(f"无法读取注册表 {path}: {exc}") from exc


def load_registry(path):
    return read_snapshot(path)[0]


@contextmanager
def registry_lock(path, timeout=5):
    """An OS lock survives neither normal exit nor a crashed writer.

    Keep the sidecar inode: unlinking it after release can create two locks
    for one registry when another process is already waiting on the old file.
    """
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise RegistryConflict("注册表正被另一进程修改，请稍后重新读取并重试") from exc
                time.sleep(.05)
        yield  # Closing the descriptor releases the kernel lock on both OSes.


def _serialize(data):
    try:
        return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RegistryError("档案包含无法保存的 JSON 值；未修改原文件") from exc


def _atomic_write(path, content, replace=False, mode=None, expected_revision=None):
    """Publish complete bytes from the same directory; never truncate readers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        deadline = time.monotonic() + 1
        while True:
            if replace and expected_revision is not None:
                current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                if current != expected_revision:
                    raise RegistryConflict("提交时发现档案已变化；未覆盖，请重新读取")
            try:
                if replace:
                    os.replace(temporary, path)
                elif os.name == "nt":
                    os.rename(temporary, path)  # Windows rename refuses an existing target.
                else:
                    os.link(temporary, path)  # Atomic no-clobber publication on local POSIX filesystems.
                break
            except PermissionError as exc:
                # Windows scanners/readers can briefly deny FILE_SHARE_DELETE.
                # Retry only the filesystem publish, never a device command.
                if getattr(exc, "winerror", None) not in (5, 32, 33) or time.monotonic() >= deadline:
                    raise
                time.sleep(.025)
    finally:
        if temporary.exists() and mode is not None and not mode & stat.S_IWUSR:
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        temporary.unlink(missing_ok=True)


def _backup(path, raw, revision):
    backup = path.parent / ".wuwu-backups" / f"{path.name}.{revision}.bak"
    if backup.exists():
        if backup.read_bytes() != raw:
            raise RegistryError(f"备份内容校验失败，未修改注册表: {backup}")
    else:
        _atomic_write(backup, raw)
    return backup


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and "\0" not in value


def _number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_value(value, spec, label):
    kind = spec.get("type")
    valid = {"integer": type(value) is int,
             "number": _number(value),
             "string": isinstance(value, str) and "\0" not in value,
             "boolean": type(value) is bool}
    if not valid.get(kind, False):
        raise RegistryError(f"{label}: 需要 {kind} 类型")
    if kind in ("integer", "number"):
        if "minimum" in spec and value < spec["minimum"]:
            raise RegistryError(f"{label}: 不得小于 {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise RegistryError(f"{label}: 不得大于 {spec['maximum']}")
    if "enum" in spec and value not in spec["enum"]:
        raise RegistryError(f"{label}: 必须是 {spec['enum']} 之一")
    return value


def _validate_spec(spec, label):
    if not isinstance(spec, dict) or spec.get("type") not in ("integer", "number", "string", "boolean"):
        raise RegistryError(f"{label}: 参数必须包含 type（integer / number / string / boolean）")
    unknown = set(spec) - ARG_FIELDS
    if unknown:
        raise RegistryError(f"{label}: 不支持的参数约束字段 {sorted(unknown)}；请检查字段名")
    if not _text(spec.get("description")):
        raise RegistryError(f"{label}: 缺少 description")
    for bound in ("minimum", "maximum"):
        if bound in spec and (spec["type"] not in ("integer", "number") or not _number(spec[bound])):
            raise RegistryError(f"{label}: {bound} 必须是有限数值，且只能用于数值参数")
    if "minimum" in spec and "maximum" in spec and spec["minimum"] > spec["maximum"]:
        raise RegistryError(f"{label}: minimum 大于 maximum")
    if "enum" in spec:
        if not isinstance(spec["enum"], list) or not spec["enum"]:
            raise RegistryError(f"{label}: enum 必须是非空数组")
        for value in spec["enum"]:
            validate_value(value, {k: v for k, v in spec.items() if k != "enum"}, label)
    if "default" in spec:
        validate_value(spec["default"], spec, label + ".default")


def _validate_command(command, label, warnings):
    if isinstance(command, str) and _text(command):
        warnings.append(f"{label}: 旧格式 run 字符串，仅供迁移；plan/run 需要 argv")
        return
    if not isinstance(command, dict) or not _text(command.get("desc")):
        raise RegistryError(f"{label}: 命令必须包含 desc")
    for flag in ("idempotent", "read_only"):
        if flag in command and type(command[flag]) is not bool:
            raise RegistryError(f"{label}.{flag}: 必须是布尔值")
    if "timeout" in command and (not _number(command["timeout"]) or not 0 < command["timeout"] <= 3600):
        raise RegistryError(f"{label}.timeout: 必须大于 0 且不超过 3600 秒")
    if "argv" not in command:
        if not _text(command.get("run")):
            raise RegistryError(f"{label}: 缺少 argv 或旧格式 run")
        warnings.append(f"{label}: 旧格式 run，仅供迁移；plan/run 需要 argv")
        return
    argv = command["argv"]
    if not isinstance(argv, list) or not argv or any(not isinstance(v, str) or "\0" in v for v in argv):
        raise RegistryError(f"{label}.argv: 必须是非空字符串数组，不能含 NUL")
    if not _text(argv[0]):
        raise RegistryError(f"{label}.argv: 可执行程序不能为空")
    specs = command.get("args", {})
    if not isinstance(specs, dict):
        raise RegistryError(f"{label}.args: 必须是对象")
    for name, spec in specs.items():
        if not isinstance(name, str) or not PARAM.fullmatch(name) or name == "python":
            raise RegistryError(f"{label}.args: 无效或保留的参数名 {name}")
        _validate_spec(spec, f"{label}.args.{name}")
    referenced = set()
    for index, arg in enumerate(argv):
        match = TOKEN.fullmatch(arg)
        if match:
            name = match[1]
            if name == "python" and index == 0:
                continue
            if index == 0 or name not in specs:
                raise RegistryError(f"{label}.argv: 未定义或不允许的占位符 {arg}")
            referenced.add(name)
        elif "{" in arg or "}" in arg:
            raise RegistryError(f"{label}.argv: 占位符必须独占一个参数: {arg}")
    if set(specs) != referenced:
        raise RegistryError(f"{label}.args: 存在未用于 argv 的参数 {sorted(set(specs) - referenced)}")


def validate_registry(data):
    """Return legacy-format warnings; raise RegistryError on invalid data."""
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        raise RegistryError("注册表必须是包含 devices 数组的 JSON 对象")
    if "version" in data and (type(data["version"]) is not int or data["version"] != 1):
        raise RegistryError("不支持的注册表 version；当前支持 1")
    warnings, identities = [], {}
    for index, device in enumerate(data["devices"]):
        label = f"devices[{index}]"
        if not isinstance(device, dict) or not _text(device.get("name")):
            raise RegistryError(f"{label}: 缺少 name")
        aliases = device.get("aliases", [])
        if not isinstance(aliases, list) or any(not _text(alias) for alias in aliases):
            raise RegistryError(f"{label}.aliases: 必须是非空名称组成的数组")
        for alias in [device["name"], *aliases]:
            normalized = alias.strip().casefold()
            if normalized in identities:
                raise RegistryError(f"{label}: 名称或别名重复 {alias}（已用于 {identities[normalized]}）")
            identities[normalized] = device["name"]
        if not _text(device.get("project_path")):
            raise RegistryError(f"{label}: 缺少 project_path")
        commands = device.get("commands")
        if not isinstance(commands, dict) or not commands:
            if "quick_examples" in device:
                raise RegistryError(f"{label}: 旧档案只有 quick_examples，请核对 CLI 后迁移为 commands/argv")
            raise RegistryError(f"{label}.commands: 必须至少登记一条命令")
        for name, command in commands.items():
            if not _text(name):
                raise RegistryError(f"{label}.commands: 命令名不能为空")
            _validate_command(command, f"{label}.commands.{name}", warnings)
    # _template is documentation, never a registered device.
    return warnings


def initialize(path):
    """Publish a complete empty registry, preserving any existing file."""
    path = Path(path).expanduser().resolve()
    with registry_lock(path):
        if path.is_file():
            return False
        if path.exists():
            raise RegistryError(f"注册表路径不是普通文件: {path}")
        try:
            _atomic_write(path, _serialize({"version": 1, "devices": []}))
        except FileExistsError:
            return False
        return True


def migrate_registry(source, destination, base_dir=None):
    """Copy legacy data without deleting the source or replacing user data.

    Relative project paths are anchored to the old registry before moving.
    Command schemas are preserved for a separate, explicit format migration.
    """
    source, destination = Path(source).expanduser().resolve(), Path(destination).expanduser().resolve()
    base = Path(base_dir).expanduser().resolve() if base_dir is not None else source.parent
    if source == destination:
        raise RegistryError("源档案与目标档案相同，无需迁移")
    data = load_registry(source)
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        raise RegistryError("旧档案必须包含 devices 数组；原文件保留，请先修复格式")
    for index, device in enumerate(data["devices"]):
        if not isinstance(device, dict) or not _text(device.get("project_path")):
            raise RegistryError(f"devices[{index}]: 缺少有效 project_path，无法确定迁移后的工作目录")
        project = Path(device["project_path"]).expanduser()
        if not project.is_absolute():
            device["project_path"] = str((base / project).resolve())
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except ValueError as exc:
        raise RegistryError("旧档案含非有限数值，未写入目标；请先修复 JSON 数据") from exc
    with registry_lock(destination):
        try:
            _atomic_write(destination, content.encode("utf-8"))
        except FileExistsError as exc:
            raise RegistryError(f"目标注册表已存在，未覆盖: {destination}") from exc
    return len(data["devices"])


def _device_index(data, name):
    normalized = name.strip().casefold()
    for index, device in enumerate(data["devices"]):
        if normalized in [value.strip().casefold() for value in [device["name"], *device.get("aliases", [])]]:
            return index
    raise RegistryError(f"未登记设备: {name}；用 list 查看设备，不会使用 _template")


def show_device(path, name):
    path = Path(path).expanduser().resolve()
    data, revision, _ = read_snapshot(path)
    validate_registry(data)
    return {"registry": str(path), "revision": revision, "device": data["devices"][_device_index(data, name)]}


def _edit_registry(path, action, values, name=None, revision=None, dry_run=False):
    path = Path(path).expanduser().resolve()
    if not isinstance(values, dict) or "devices" in values or "_template" in values:
        raise RegistryError("--file 需要单台设备的 JSON 对象或更新字段，不是整个注册表")
    if {"registry", "revision", "device"}.issubset(values):
        raise RegistryError("请从 show 结果中提取 device 对象或需要修改的字段，不要提交整个读取回执")
    if action == "update" and (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", revision)):
        raise RegistryError("update 需要 show 返回的 revision（64 位十六进制）")
    # A preview reads one snapshot but creates no directories, locks, or backups.
    guard = nullcontext() if dry_run else registry_lock(path)
    with guard:
        if path.exists() or action == "update":
            data, previous_revision, raw = read_snapshot(path)
            validate_registry(data)
        else:
            data, previous_revision, raw = {"version": 1, "devices": []}, None, None
        if revision is not None and revision.lower() != previous_revision:
            raise RegistryConflict("注册表已被其他会话修改；请重新 show，核对新内容后再提交")
        candidate = copy.deepcopy(data)
        if action == "register":
            candidate["devices"].append(copy.deepcopy(values))
            record = candidate["devices"][-1]
        else:
            index = _device_index(data, name)
            record = candidate["devices"][index]
            if "name" in values and values["name"] != record["name"]:
                raise RegistryError("update 不更改设备 name；请使用原设备名，别名可通过 aliases 更新")
            for key, value in values.items():
                if key in ("commands", "control", "hardware", "global_options"):
                    if not isinstance(value, dict):
                        raise RegistryError(f"{key} 更新值必须是对象")
                    existing = record.get(key, {})
                    # Commands replace as complete units: never carry an old
                    # retry flag or argument schema into a different operation.
                    record[key] = {**(existing if isinstance(existing, dict) else {}), **copy.deepcopy(value)}
                else:
                    record[key] = copy.deepcopy(value)
        warnings = validate_registry(candidate)
        changed = candidate != data
        content = _serialize(candidate)
        next_revision = hashlib.sha256(content).hexdigest() if changed else previous_revision
        result = {"action": action, "registry": str(path), "name": record["name"],
                  "previous_revision": previous_revision, "revision": next_revision,
                  "backup": None, "warnings": warnings}
        if dry_run:
            result.update(status="planned", revision=previous_revision, next_revision=next_revision, device=record)
            return result
        if not changed:
            result["status"] = "unchanged"
            return result
        if raw is not None:
            result["backup"] = str(_backup(path, raw, previous_revision))
        # Detect edits made by programs which do not use our lock whenever
        # they are visible before commit. Only cooperating writers are serialized.
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if current != previous_revision:
            raise RegistryConflict("写入前发现注册表内容变化；原修改未覆盖，请重新读取")
        mode = stat.S_IMODE(path.stat().st_mode) if raw is not None else None
        try:
            _atomic_write(path, content, replace=raw is not None, mode=mode, expected_revision=previous_revision)
        except FileExistsError as exc:
            raise RegistryConflict("注册表已被其他程序创建；未覆盖，请重新读取") from exc
        result["status"] = "registered" if action == "register" else "updated"
        return result


def register_device(path, device, dry_run=False):
    return _edit_registry(path, "register", device, dry_run=dry_run)


def update_device(path, name, changes, revision, dry_run=False):
    return _edit_registry(path, "update", changes, name=name, revision=revision, dry_run=dry_run)


def make_plan(data, registry_path, device_name, command_name, arguments=None):
    validate_registry(data)
    device = data["devices"][_device_index(data, device_name)]
    command = device["commands"].get(command_name)
    if command is None:
        raise RegistryError(f"{device['name']} 没有命令 {command_name}")
    if not isinstance(command, dict) or "argv" not in command:
        raise RegistryError("此命令是旧格式，请核对实际 CLI 后迁移为 argv；不自动拆分或执行 shell 字符串")
    arguments = {} if arguments is None else arguments
    if not isinstance(arguments, dict):
        raise RegistryError("--args 必须是 JSON 对象")
    specs = command.get("args", {})
    unknown = set(arguments) - set(specs)
    if unknown:
        raise RegistryError(f"未定义的参数: {sorted(unknown)}")
    values = {}
    for key, spec in specs.items():
        if key not in arguments and "default" not in spec:
            raise RegistryError(f"缺少参数: {key}")
        value = validate_value(arguments.get(key, spec.get("default")), spec, key)
        values[key] = str(value).lower() if type(value) is bool else str(value)
    values["python"] = sys.executable
    argv = [values[TOKEN.fullmatch(arg)[1]] if TOKEN.fullmatch(arg) else arg for arg in command["argv"]]
    project = Path(device["project_path"]).expanduser()
    if not project.is_absolute():
        project = Path(registry_path).resolve().parent / project
    if not Path(argv[0]).is_absolute() and ("/" in argv[0] or "\\" in argv[0]):
        argv[0] = str((project / argv[0]).resolve())
    return {"device": device["name"], "command": command_name,
            "cwd": str(project.resolve()), "argv": argv,
            "timeout": command.get("timeout", 30),
            "read_only": command.get("read_only", False),
            "idempotent": command.get("idempotent", False)}


def execute_plan(plan):
    """Run once. A lost acknowledgement never triggers an implicit retry."""
    if not Path(plan["cwd"]).is_dir():
        raise RegistryError(f"项目目录不存在: {plan['cwd']}")
    executable = shutil.which(plan["argv"][0]) or plan["argv"][0]
    if os.name == "nt" and Path(executable).suffix.lower() in (".cmd", ".bat"):
        raise RegistryError("Windows 批处理会再次解析参数；请登记实际可执行程序或 Python 脚本")
    environment = os.environ.copy()
    # Python defaults to the Windows ANSI code page when stdout is a pipe.
    # Keep child CLI output compatible with the registry's UTF-8 JSON output.
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        return subprocess.run([executable, *plan["argv"][1:]], cwd=plan["cwd"], shell=False,
                              timeout=plan["timeout"], check=False, env=environment).returncode
    except subprocess.TimeoutExpired as exc:
        raise RegistryError("命令超时，设备执行状态未知；未自动重试。请先查询状态或检查设备") from exc
    except OSError as exc:
        raise RegistryError(f"无法启动命令: {exc}") from exc


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path,
                        help="注册表路径；默认 WUWU_DEVICES_FILE 或 ~/.wuwu-intelligence/devices.json")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "validate", "list"):
        sub.add_parser(action)
    show = sub.add_parser("show", help="读取完整设备档案及用于更新的 revision")
    show.add_argument("device")
    register = sub.add_parser("register", help="从单台设备 JSON 文件登记设备，不覆盖已有设备")
    register.add_argument("--file", type=Path, required=True)
    register.add_argument("--dry-run", action="store_true", help="只预览，不写入任何文件")
    update = sub.add_parser("update", help="按读取时的版本更新设备，保留未涉及的数据")
    update.add_argument("device")
    update.add_argument("--file", type=Path, required=True, help="仅包含需要更新的字段")
    update.add_argument("--if-revision", required=True, help="show 返回的 revision")
    update.add_argument("--dry-run", action="store_true", help="只预览，不写入任何文件")
    migration = sub.add_parser("migrate", help="把旧档案复制到独立数据目录，保留原文件")
    migration.add_argument("--from", dest="source", type=Path, default=LEGACY_REGISTRY,
                           help="旧档案路径，默认当前 Skill 安装目录中的 devices.json")
    migration.add_argument("--base-dir", type=Path,
                           help="迁移已挪位置的备份时，指定原注册表目录，用于解析相对项目路径")
    for action in ("plan", "run"):
        command = sub.add_parser(action)
        command.add_argument("device", help="设备 name 或完整别名")
        command.add_argument("command", help="已登记命令名")
        command.add_argument("--args", default="{}", help='参数 JSON，如 {"r":255,"g":0,"b":0}')
    options = parser.parse_args(argv)
    try:
        options.registry, legacy = select_registry(options.registry, options.action)
        if legacy:
            print(f"WARN 正在读取旧安装目录档案 {options.registry}；请运行 migrate，避免升级时丢失", file=sys.stderr)
        if options.action == "init":
            created = initialize(options.registry)
            print(("已创建空注册表: " if created else "注册表已存在，保留原文件: ") + str(options.registry))
            return 0
        if options.action == "migrate":
            count = migrate_registry(options.source, options.registry, options.base_dir)
            print(f"已迁移 {count} 台设备到 {options.registry}；原档案保留，请运行 validate 检查命令格式")
            return 0
        if options.action == "show":
            print(json.dumps(show_device(options.registry, options.device), ensure_ascii=False, indent=2))
            return 0
        if options.action in ("register", "update"):
            values = load_registry(options.file)
            if options.action == "register":
                result = register_device(options.registry, values, dry_run=options.dry_run)
            else:
                result = update_device(options.registry, options.device, values, options.if_revision,
                                       dry_run=options.dry_run)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        data = load_registry(options.registry)
        warnings = validate_registry(data)
        if options.action == "validate":
            for warning in warnings:
                print("WARN " + warning)
            print(f"OK {len(data['devices'])} 台已登记设备")
        elif options.action == "list":
            print(json.dumps([{"name": d["name"], "aliases": d.get("aliases", []),
                               "commands": list(d["commands"])} for d in data["devices"]],
                             ensure_ascii=False, indent=2))
        else:
            plan = make_plan(data, options.registry, options.device, options.command, parse_json(options.args))
            if options.action == "run":
                return execute_plan(plan)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    except RegistryConflict as exc:
        print(f"ERROR E_CONFLICT: {exc}", file=sys.stderr)
        return 2
    except (RegistryError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
