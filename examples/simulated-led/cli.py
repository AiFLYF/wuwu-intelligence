#!/usr/bin/env python3
"""CLI for the bundled loopback-only simulator, not a physical device driver."""

import argparse
import json
import math
import socket
import sys
import time
import uuid


class DeviceError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def send(port, payload, timeout):
    request_id = uuid.uuid4().hex
    request = {"id": request_id, **payload}
    deadline = time.monotonic() + timeout
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
            connection.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
            buffer = bytearray()
            while b"\n" not in buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                connection.settimeout(remaining)
                # Small reads intentionally exercise split JSON / UTF-8 frames.
                chunk = connection.recv(17)
                if not chunk:
                    raise DeviceError("E_CONNECTION", "连接已关闭，未收到完整响应")
                buffer.extend(chunk)
                if len(buffer) > 4096:
                    raise DeviceError("E_JSON", "响应超过长度上限")
        try:
            response = json.loads(buffer.split(b"\n", 1)[0].decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise DeviceError("E_JSON", "响应不是合法的 UTF-8 JSON") from exc
        if not isinstance(response, dict) or response.get("id") != request_id or type(response.get("ok")) is not bool:
            raise DeviceError("E_JSON", "响应格式或请求编号不匹配")
        return response
    except TimeoutError as exc:
        raise DeviceError("E_TIMEOUT", "响应超时，执行结果未知；未重试") from exc
    except OSError as exc:
        raise DeviceError("E_CONNECTION", "无法连接本机模拟设备") from exc


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=3)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "fail", "malformed"):
        sub.add_parser(name)
    color = sub.add_parser("color")
    for component in ("r", "g", "b"):
        color.add_argument(component, type=int)
    sub.add_parser("brightness").add_argument("value", type=int)
    sub.add_parser("text").add_argument("value")
    for name in ("increment", "delayed_increment"):
        sub.add_parser(name).add_argument("amount", type=int, nargs="?", default=1)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535 or not math.isfinite(options.timeout) or options.timeout <= 0:
        parser.error("invalid port or timeout")
    payload = {"cmd": options.command}
    for field in ("r", "g", "b", "value", "amount"):
        if hasattr(options, field):
            payload[field] = getattr(options, field)
    try:
        response = send(options.port, payload, options.timeout)
        print(json.dumps(response, ensure_ascii=False))
        return 0 if response["ok"] else 4
    except DeviceError as exc:
        print(json.dumps({"ok": False, "simulation": True, "code": exc.code, "error": str(exc)}, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
