#!/usr/bin/env python3
"""self_check.py — ESP32 灯板示例的一步式环境自检（不改硬件、不烧录）。

    python self_check.py            # 只查工具链与固件配置
    python self_check.py --compile  # 再实际编译一次固件（最严格的静态验证）

任何一项不过都会给出具体修法。本机没装工具链时会明确报「未验证」而不是猜。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIRMWARE = HERE / "firmware" / "led_matrix"
SKETCH = FIRMWARE / "led_matrix.ino"

EXPECTED_CORE = "2.3.4"
EXPECTED_LIBS = {"FastLED": "3.7.8", "ArduinoJson": "7.2.0"}
FQBN = "esp32:esp32:esp32s3"

problems = []


def report(ok, item, detail, fix=None):
    print(f"{'OK  ' if ok else 'FAIL'} {item}: {detail}")
    if not ok:
        problems.append((item, fix))


def run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=300)
    except OSError:
        return None


def main():
    compile_too = "--compile" in sys.argv

    cli = shutil.which("arduino-cli")
    if not cli:
        report(False, "arduino-cli", "不在 PATH 上",
               "安装 arduino-cli 后重试：https://arduino.github.io/arduino-cli/latest/installation/")
        return finish()
    result = run([cli, "version", "--format", "json"])
    version = json.loads(result.stdout).get("VersionString", "?") if result and result.returncode == 0 else "?"
    report(True, "arduino-cli", version)

    result = run([cli, "core", "list", "--format", "json"])
    payload = json.loads(result.stdout) if result and result.returncode == 0 else {}
    installed = {c["id"]: c["installed_version"] for c in payload.get("platforms", [])}
    actual = installed.get("esp32:esp32")
    report(actual == EXPECTED_CORE, "esp32 core",
           actual or "未安装",
           None if actual == EXPECTED_CORE else
           f"arduino-cli core install esp32:esp32@{EXPECTED_CORE}")

    result = run([cli, "lib", "list", "--format", "json"])
    payload = json.loads(result.stdout) if result and result.returncode == 0 else {}
    libs = {entry["library"]["name"]: entry["library"]["version"]
            for entry in payload.get("installed_libraries", [])}
    for name, want in EXPECTED_LIBS.items():
        actual = libs.get(name)
        report(actual == want, f"lib {name}", actual or "未安装",
               None if actual == want else f'arduino-cli lib install "{name}@{want}"')

    sketch = SKETCH.read_text(encoding="utf-8") if SKETCH.exists() else ""
    report(bool(sketch), "firmware", str(SKETCH.relative_to(HERE)))
    if sketch:
        report('"你的WiFi"' not in sketch, "WiFi 凭据",
               "仍是占位符" if "你的WiFi" in sketch else "已改为本地网络",
               "把 WIFI_SSID/WIFI_PASS 改成本地网络（正式项目挪进 config.h 并 gitignore）")

    if compile_too and not problems:
        print(f"\n编译固件（{FQBN}）……")
        result = run([cli, "compile", "--fqbn", FQBN, str(FIRMWARE)])
        report(result is not None and result.returncode == 0, "compile",
               "通过" if result and result.returncode == 0 else (result.stderr or "?")[-400:],
               "按上方编译输出修正固件或环境")

    return finish()


def finish():
    if problems:
        print("\n未通过，逐项修复：")
        for item, fix in problems:
            print(f"  - {item}: {fix or '见上'}")
        return 2
    print("\n全部通过。注意：这只验证工具链与静态配置，"
          "烧录与灯效仍需实机核对（见 README 的验证状态声明）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
