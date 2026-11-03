#!/usr/bin/env python3
"""led_cli.py — ESP32-S3 + WS2812B-64 灯板的最小 CLI（标准库，TCP 8888，单行 JSON）。

    python pc/led_cli.py --ip 192.168.1.50 status
    python pc/led_cli.py --ip 192.168.1.50 color 255 0 0
    python pc/led_cli.py --ip 192.168.1.50 brightness 120
    python pc/led_cli.py --ip 192.168.1.50 off

--ip 成功一次后写入同目录 device.json，之后可省略；--forget 清除。
本骨架尚未在真实硬件上验证。
"""

import argparse
import json
import socket
import sys
from pathlib import Path

DEVICE_FILE = Path(__file__).with_name("device.json")
DEFAULT_PORT = 8888


class LedError(Exception):
    pass


def resolve_ip(explicit):
    if explicit:
        return explicit
    try:
        saved = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
        if saved.get("ip"):
            return saved["ip"]
    except (OSError, ValueError):
        pass
    raise LedError("缺少 --ip；看串口监视器（115200）里打印的 IP，成功后会自动记住")


def remember_ip(ip):
    DEVICE_FILE.write_text(json.dumps({"ip": ip}, indent=2) + "\n", encoding="utf-8")


def request(ip, payload, timeout=8):
    line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with socket.create_connection((ip, DEFAULT_PORT), timeout=timeout) as sock:
            sock.sendall(line)
            data = b""
            while not data.endswith(b"\n"):
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk
    except OSError as exc:
        raise LedError(f"连不上 {ip}:{DEFAULT_PORT}（{exc}）。先 ping 设备，"
                       "不通就看串口里的当前 IP；通就确认固件里 TCP server 已启动") from exc
    try:
        response = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise LedError(f"响应不是合法 JSON: {data!r}") from exc
    if not response.get("ok"):
        raise LedError(f"设备拒绝: {response.get('error', '未知错误')}")
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", help="设备地址；成功一次后自动记住")
    parser.add_argument("--forget", action="store_true", help="清除记住的 IP")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status")
    color = sub.add_parser("color")
    color.add_argument("r", type=int)
    color.add_argument("g", type=int)
    color.add_argument("b", type=int)
    brightness = sub.add_parser("brightness")
    brightness.add_argument("value", type=int)
    sub.add_parser("off")
    options = parser.parse_args()

    if options.forget:
        DEVICE_FILE.unlink(missing_ok=True)
        print("已清除记住的 IP")
        return 0
    if options.command is None:
        parser.error("缺少命令：status / color / brightness / off")
    try:
        if options.command == "status":
            payload = {"cmd": "status"}
        elif options.command == "color":
            for name in ("r", "g", "b"):
                value = getattr(options, name)
                if not 0 <= value <= 255:
                    raise LedError(f"{name}={value} 超出 0-255")
            payload = {"cmd": "color", "r": options.r, "g": options.g, "b": options.b}
        elif options.command == "brightness":
            if not 0 <= options.value <= 255:
                raise LedError("亮度需要 0-255")
            payload = {"cmd": "brightness", "value": options.value}
        else:
            payload = {"cmd": "off"}
        ip = resolve_ip(options.ip)
        response = request(ip, payload)
    except LedError as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 2
    remember_ip(ip)
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
