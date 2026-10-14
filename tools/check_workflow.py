#!/usr/bin/env python3
"""Exercise an installed Skill through a real loopback TCP device and CLI.

No physical hardware or user registry is accessed. Results and a generated
manual remain under .workbuddy/verification/ for inspection.
"""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/wuwu-intelligence"
EXAMPLE = ROOT / "examples/simulated-led"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_text(argv):
    if os.name == "nt":
        return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in argv)
    return shlex.join(argv)


def example_device(project, port):
    def integer(description, low=0, high=255):
        return {"type": "integer", "description": description, "minimum": low, "maximum": high}

    definitions = {
        "status": ("查询模拟设备状态", [], {}, True, True),
        "color": ("将模拟灯板设为指定 RGB", ["{r}", "{g}", "{b}"],
                  {key: integer(key) for key in ("r", "g", "b")}, False, True),
        "brightness": ("设置模拟亮度", ["{value}"], {"value": integer("亮度")}, False, True),
        "text": ("保存模拟显示文字", ["{value}"], {"value": {"type": "string", "description": "文字"}}, False, True),
        "increment": ("将模拟计数器加一", ["{amount}"], {"amount": {**integer("增量", 1, 10), "default": 1}}, False, False),
        "delayed_increment": ("故障测试：计数后延迟响应", ["1"], {}, False, False),
        "fail": ("故障测试：模拟外设错误", [], {}, True, True),
        "malformed": ("故障测试：返回非法 JSON", [], {}, True, True),
    }
    commands = {}
    for name, (description, tail, arguments, read_only, idempotent) in definitions.items():
        commands[name] = {
            "desc": description,
            "argv": ["{python}", "cli.py", "--port", str(port), "--timeout", "8", name, *tail],
            "args": arguments, "read_only": read_only, "idempotent": idempotent,
            "timeout": 1.5 if name == "delayed_increment" else 12,
        }
    return {"name": "sim_led", "aliases": ["模拟灯板"], "description": "本机 TCP 软件模拟设备",
            "project_path": str(project), "control": {"cli": "cli.py", "transport": f"tcp:{port}"},
            "commands": commands, "manual": "docs/manual.html", "simulation": True}


def generate_manual(skill, project, device, port):
    template = (skill / "references/manual-template.html").read_text(encoding="utf-8")
    samples = {"color": {"r": 255, "g": 0, "b": 0}, "brightness": {"value": 80},
               "text": {"value": "你好，模拟灯板"}, "increment": {"amount": 1}}
    sections, sayings = [], []
    for name, command in device["commands"].items():
        values = {"python": sys.executable, **samples.get(name, {})}
        argv = [str(values[value[1:-1]]) if value.startswith("{") else value for value in command["argv"]]
        desc = html.escape(command["desc"])
        sections.append(f'<h3>{name} · {desc}</h3><div class="cmd">{html.escape(command_text(argv))}'
                        '<button data-copy>复制</button></div>')
        sayings.append(f'<tr><td><span class="say">{desc}</span></td><td>{name}（仅软件模拟）</td></tr>')
    start = template.index('  <h3>{{CMD_1_NAME}}')
    end = template.index('  <h3>通用参数</h3>', start)
    template = template[:start] + "\n".join(sections) + "\n" + template[end:]
    start = template.index('<tbody>', template.index('id="say"')) + len('<tbody>')
    end = template.index('</tbody>', start)
    template = template[:start] + "\n".join(sayings) + template[end:]
    # Only retain error codes actually used by this simulator.
    template = re.sub(r'^\s*<tr>[^\n]*<code>E_BUSY</code>[^\n]*</tr>\n?', '', template, flags=re.M)
    connection_row = '<tr><td><code>E_CONNECTION</code></td><td>无法连接或连接中断</td><td>确认本机模拟服务已启动、端口正确</td></tr>\n'
    code_pos = template.index('      <tr><td><span class="dot warn"></span><code>E_JSON</code>')
    template = template[:code_pos] + connection_row + template[code_pos:]
    fields = {
        "DEVICE_NAME": "模拟灯板 · 软件验证", "ONE_LINE_INTRO": "本页来自实际执行过的本机 TCP 模拟流程，不代表真实硬件。",
        "ACCENT": "#7c3aed", "ACCENT_2": "#4338ca", "HERO_A": "#17102b", "HERO_B": "#102338", "HERO_MODE": "",
        "MCU": "Python 软件设备", "TOOLCHAIN": "Python 标准库", "SIGNAL_PIN": "无物理引脚",
        "POWER": "无需外接电源", "TRANSPORT": f"TCP 127.0.0.1:{port}",
        "ASCII_WIRING": "注册表工具 → 本地 CLI → TCP 127.0.0.1 → 模拟设备状态",
        "START_STEP_1": "本次自动验收结束后会关闭模拟服务，重新试用时先启动它。",
        "START_STEP_2": command_text([sys.executable, str(EXAMPLE / "device.py"), "--port", str(port)]),
        "START_STEP_3": "在下方项目目录运行 CLI；每条响应都带有 simulation: true。",
        "PROJECT_PATH": str(project), "FW_VERSION": "simulated-led v1（软件模拟）", "DATE": "本次软件验收",
        "OPT_1": "--port", "OPT_1_DESC": f"本次模拟服务端口 {port}",
        "OPT_2": "--timeout", "OPT_2_DESC": "客户端响应等待上限（秒）；与注册表的进程超时分别生效",
        "FAQ_1_Q": "为什么连接失败？", "FAQ_1_WHY": "模拟进程可能已关闭。", "FAQ_1_FIX": "按开始步骤重新启动服务并核对端口。",
        "FAQ_2_Q": "为什么真实灯板没有变化？", "FAQ_2_WHY": "此示例没有连接物理设备。", "FAQ_2_FIX": "真实硬件需要对应驱动与固件，再按接入指南登记。",
        "FAQ_3_Q": "延迟命令超时后能立即重试吗？", "FAQ_3_WHY": "模拟计数已经改变，但响应可能迟到。", "FAQ_3_FIX": "先用 status 回读 counter，避免重复增加。",
        "SAFETY_1": "本例只使用 127.0.0.1，故障注入命令仅适用于这个软件模拟器。",
        "SAFETY_2": "模拟状态存于内存，重启服务会恢复初始值。",
    }
    def replace(match):
        key = match[1]
        require(key in fields, f"Missing manual value: {key}")
        return html.escape(fields[key], quote=True)
    rendered = re.sub(r"\{\{([A-Z0-9_]+)\}\}", replace, template)
    require("{{" not in rendered, "Manual still contains placeholders")
    path = project / "docs/manual.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return path


def check(installed, output):
    workspace = Path(tempfile.mkdtemp(prefix="workflow-", dir=output)).resolve()
    report = {"status": "running", "simulation": True, "workspace": str(workspace), "steps": []}
    server = None
    log = None
    try:
        if installed:
            skill = installed.resolve()
        else:
            skill = workspace / "installed/skills/wuwu-intelligence"
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("devices.json", "device.json", "__pycache__", ".env*", "*.local.json", "*.json.lock", ".*.json.*.tmp", ".wuwu-backups"))
        script = skill / "scripts/device_registry.py"
        require(script.is_file() and (skill / "SKILL.md").is_file(), "Skill installation is incomplete")
        report["skill"] = str(skill)
        report["script_sha256"] = hashlib.sha256(script.read_bytes()).hexdigest()
        registry = workspace / "user-data/devices.json"
        environment = {**os.environ, "WUWU_DEVICES_FILE": str(registry)}

        def invoke(name, arguments, expected=0, target=None):
            argv = [sys.executable, str(script)]
            if target:
                argv += ["--registry", str(target)]
            argv += arguments
            started = time.monotonic()
            result = subprocess.run(argv, cwd=workspace, env=environment, capture_output=True, timeout=20)
            step = {"name": name, "exit_code": result.returncode, "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8")}
            report["steps"].append(step)
            require(result.returncode == expected, f"{name}: expected exit {expected}, got {result.returncode}: {step['stderr']}")
            print(f"PASS {name}", flush=True)
            return step

        def run(name, command, arguments=None, expected=0):
            return invoke(name, ["run", "模拟灯板", command, "--args", json.dumps(arguments or {}, ensure_ascii=False)], expected)

        invoke("initialize isolated registry", ["init"])
        require(json.loads(invoke("empty device list", ["list"])["stdout"]) == [], "New registry must be empty")
        project = workspace / "设备 项目"
        project.mkdir()
        shutil.copy2(EXAMPLE / "cli.py", project / "cli.py")
        ready_file, events = workspace / "ready.json", workspace / "events.jsonl"
        log = (workspace / "server.log").open("wb")
        server = subprocess.Popen([sys.executable, str(EXAMPLE / "device.py"), "--port", "0",
                                   "--ready-file", str(ready_file), "--events", str(events)],
                                  cwd=workspace, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while True:
            require(server.poll() is None and time.monotonic() < deadline, "Simulator did not start; inspect server.log")
            if ready_file.exists():
                try:
                    ready = json.loads(ready_file.read_text(encoding="utf-8"))
                    break
                except json.JSONDecodeError:
                    pass  # The writer may have opened the readiness file but not finished flushing.
            time.sleep(.03)
        device = example_device(project, ready["port"])
        definition = workspace / "new-device.json"
        write_json(definition, device)
        empty_bytes = registry.read_bytes()
        draft = invoke("preview device registration", ["register", "--file", str(definition), "--dry-run"])
        require(json.loads(draft["stdout"])["status"] == "planned", "Registration preview did not produce a plan")
        require(registry.read_bytes() == empty_bytes, "Registration preview modified the registry")
        receipt = json.loads(invoke("register through the public CLI", ["register", "--file", str(definition)])["stdout"])
        require(Path(receipt["backup"]).read_bytes() == empty_bytes, "Registration did not back up the original")
        snapshot = json.loads(invoke("read editable device snapshot", ["show", "模拟灯板"])["stdout"])
        require(snapshot["revision"] == receipt["revision"], "Read revision does not match the committed version")
        original = registry.read_bytes()
        invoke("validate registered device", ["validate"])
        invoke("repeat initialization preserves devices", ["init"])
        require(registry.read_bytes() == original, "Initialization changed existing data")
        require(len(json.loads(invoke("list registered device", ["list"])["stdout"])) == 1, "Device not registered")
        changes = workspace / "device-changes.json"
        dim = {**device["commands"]["brightness"], "desc": "将模拟亮度设为 64",
               "argv": ["{python}", "cli.py", "--port", str(ready["port"]), "brightness", "64"], "args": {}}
        write_json(changes, {"commands": {"dim": dim}, "description": "已通过登记工具扩展的模拟设备"})
        update_args = ["update", "模拟灯板", "--file", str(changes), "--if-revision", snapshot["revision"]]
        invoke("preview device update", [*update_args, "--dry-run"])
        require(registry.read_bytes() == original, "Update preview changed existing data")
        updated = json.loads(invoke("update without replacing unrelated commands", update_args)["stdout"])
        require(Path(updated["backup"]).read_bytes() == original, "Update backup did not preserve the previous version")
        stable = registry.read_bytes()
        conflict = invoke("reject a stale editing session", update_args, expected=2)
        require("E_CONFLICT" in conflict["stderr"] and registry.read_bytes() == stable, "Stale update overwrote current data")
        device = json.loads(invoke("read updated device", ["show", "模拟灯板"])["stdout"])["device"]
        require(len(device["commands"]) == 9 and "color" in device["commands"], "Update lost unrelated commands")
        require(json.loads(run("execute the newly registered command", "dim")["stdout"])["brightness"] == 64, "New command is not usable")
        require(json.loads(run("initial TCP status", "status")["stdout"])["simulation"], "Not a simulator response")
        before = events.read_bytes()
        plan = invoke("preview has no device I/O", ["plan", "模拟灯板", "color", "--args", '{"r":255,"g":0,"b":0}'])
        require(json.loads(plan["stdout"])["cwd"] == str(project), "Working directory is incorrect")
        require(events.read_bytes() == before, "Preview contacted the device")
        run("invalid arguments never reach the device", "color", {"r": 256, "g": 0, "b": 0}, expected=2)
        require(events.read_bytes() == before, "Invalid arguments reached the device")
        run("execute RGB command", "color", {"r": 255, "g": 0, "b": 0})
        require(json.loads(run("read back RGB state", "status")["stdout"])["rgb"] == [255, 0, 0], "Color was not applied")
        require(json.loads(run("zero brightness", "brightness", {"value": 0})["stdout"])["brightness"] == 0, "Zero was lost")
        message = "你好🙂 & ; $(literal) 'quoted'\n第二行"
        require(json.loads(run("UTF-8 and literal arguments", "text", {"value": message})["stdout"])["text"] == message, "Text changed in transit")
        require(json.loads(run("device error and exit code", "fail", expected=4)["stdout"])["code"] == "E_HW", "Device error was lost")
        require(json.loads(run("malformed protocol response", "malformed", expected=3)["stdout"])["code"] == "E_JSON", "Malformed response was accepted")
        timeout = run("real process timeout without retry", "delayed_increment", expected=2)
        require("状态未知" in timeout["stderr"], "Timeout did not explain unknown state")
        require(json.loads(run("read back after lost acknowledgement", "status")["stdout"])["counter"] == 1, "Timed-out action repeated or never reached the device")
        received = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        require(sum(request["cmd"] == "delayed_increment" for request in received) == 1, "Timed-out request was retried")

        old = workspace / "legacy/devices.json"
        legacy = json.loads(registry.read_text(encoding="utf-8"))
        legacy["devices"][0]["project_path"] = "../设备 项目"
        write_json(old, legacy)
        source_bytes = old.read_bytes()
        migrated = workspace / "migrated/devices.json"
        invoke("migrate without deleting source", ["migrate", "--from", str(old)], target=migrated)
        require(old.read_bytes() == source_bytes, "Migration modified its source")
        migration_plan = json.loads(invoke("migration preserves relative paths", ["plan", "模拟灯板", "status"], target=migrated)["stdout"])
        require(migration_plan["cwd"] == str(project), "Migration changed path meaning")
        migrated_bytes = migrated.read_bytes()
        invoke("migration never overwrites a target", ["migrate", "--from", str(old)], expected=2, target=migrated)
        require(migrated.read_bytes() == migrated_bytes, "Migration overwrote a target")
        manual = generate_manual(skill, project, device, ready["port"])
        report["manual"] = str(manual)
        print("PASS generate complete device manual", flush=True)
        server.terminate()
        server.wait(timeout=5)
        require(json.loads(run("offline service produces a real failure", "status", expected=3)["stdout"])["code"] == "E_CONNECTION", "Offline state reported success")
        report["status"] = "passed"
        report["requests_received"] = len(received)
        return_code = 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        print("FAIL " + report["error"], file=sys.stderr)
        return_code = 1
    finally:
        if server and server.poll() is None:
            server.terminate()
            server.wait(timeout=5)
        if log:
            log.close()
        write_json(workspace / "report.json", report)
        write_json(output / "latest-workflow.json", report)
        print(f"Report: {workspace / 'report.json'}", flush=True)
    return return_code


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-skill", type=Path, help="Use this installed Skill instead of copying the repository Skill")
    parser.add_argument("--output", type=Path, default=ROOT / ".workbuddy/verification")
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    return check(options.installed_skill, output)


if __name__ == "__main__":
    raise SystemExit(main())
