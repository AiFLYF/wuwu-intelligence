#!/usr/bin/env python3
"""Validate Agent Skills metadata and bundled references.

Usage: python tools/validate_skill.py [skill-or-collection ...]
Install dependencies: python -m pip install -r requirements-dev.txt
"""

import argparse
import glob
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def parse_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, "frontmatter 必须从第一行 --- 开始，并以单独一行 --- 结束"
    try:
        import yaml
    except ImportError:
        return None, "缺少 PyYAML；请运行 python -m pip install -r requirements-dev.txt"

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str):
                raise ValueError("YAML 字段名必须是字符串")
            if key in result:
                raise ValueError(f"YAML 字段重复: {key}")
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        data = yaml.load(match[1], Loader=UniqueLoader)
        if not isinstance(data, dict):
            return None, "frontmatter 必须是键值映射"
        return data, None
    except (yaml.YAMLError, ValueError, TypeError) as exc:
        return None, f"YAML 解析失败: {exc}"


def check(skill_dir):
    path = Path(skill_dir).resolve()
    file = path / "SKILL.md"
    errors, warnings = [], []
    try:
        text = file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return [f"{file}: 无法读取 SKILL.md: {exc}"], []
    metadata, error = parse_frontmatter(text)
    if error:
        return [f"{file}: {error}"], []
    name, desc = metadata.get("name"), metadata.get("description")
    if not isinstance(name, str) or not name:
        errors.append("缺少字符串 name")
    else:
        if len(name) > 64 or not NAME_RE.fullmatch(name):
            errors.append(f"name 不合规（仅小写字母/数字/单个连字符，≤64）: {name}")
        if name != path.name:
            errors.append(f"name（{name}）与目录名（{path.name}）不一致")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("缺少字符串 description")
    elif len(desc) > 1024:
        errors.append(f"description 超过 1024 字符（当前 {len(desc)}）")
    for key in ("compatibility", "license", "allowed-tools"):
        if key in metadata and (not isinstance(metadata[key], str) or not metadata[key].strip()):
            errors.append(f"{key} 必须是非空字符串")
    compat = metadata.get("compatibility")
    if isinstance(compat, str) and len(compat) > 500:
        errors.append(f"compatibility 超过 500 字符（当前 {len(compat)}）")
    if "metadata" in metadata:
        extra_metadata = metadata["metadata"]
        if not isinstance(extra_metadata, dict) or any(not isinstance(v, str) for v in extra_metadata.values()):
            errors.append("metadata 必须是字符串到字符串的映射（版本号请加引号）")
    extra = set(metadata) - ALLOWED
    if extra:
        warnings.append(f"含非标准字段（跨 agent 可能被拒绝）: {sorted(extra)}")

    body = text[FRONTMATTER_RE.match(text).end():]
    if len(body.splitlines()) > 500:
        warnings.append("SKILL.md 正文超过建议的 500 行，长内容应拆进 references/")
    # Check bundled references, not hypothetical project paths inside examples.
    links = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", body)
    links += re.findall(r"`((?:references|scripts|assets)/[^`\s]+)`", body)
    for ref in sorted(set(links)):
        parsed = urlsplit(ref.strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        relative = unquote(parsed.path)
        target = (path / relative).resolve()
        if not target.is_relative_to(path):
            errors.append(f"引用超出 skill 目录: {ref}")
        elif not target.exists():
            errors.append(f"SKILL.md 引用了不存在的文件: {ref}")
    return ([f"{file}: {e}" for e in errors], [f"{file}: {w}" for w in warnings])


def discover(path):
    """Accept a single skill, a collection, or this repository's root."""
    if (path / "SKILL.md").is_file() or not path.is_dir():
        return [path]
    if (path / "skills").is_dir():
        path = path / "skills"
    # A skill missing SKILL.md must fail instead of silently disappearing.
    return [p for p in sorted(path.iterdir()) if p.is_dir()
            and not p.name.startswith(".") and p.name != "__pycache__"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=[str(ROOT / "skills")])
    options = parser.parse_args(argv)
    errors = 0
    checked = set()
    for pattern in options.paths:
        for value in glob.glob(pattern) or [pattern]:
            path = Path(value).resolve()
            targets = discover(path)
            if not targets:
                print(f"FAIL {path}: 目录下没有任何 skill")
                errors += 1
            for target in targets:
                if target in checked:
                    continue
                checked.add(target)
                errs, warns = check(target)
                for warning in warns:
                    print("WARN " + warning)
                for error in errs:
                    print("FAIL " + error)
                if not errs:
                    print(f"OK   {target}")
                errors += len(errs)
    print("全部通过" if not errors else f"共 {errors} 个错误")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
