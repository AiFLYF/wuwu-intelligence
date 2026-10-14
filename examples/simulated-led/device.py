#!/usr/bin/env python3
"""A loopback-only, stateful LED simulator. It never touches physical hardware."""

import argparse
import json
from pathlib import Path
import socketserver
import threading
import time

MAX_LINE = 4096


class DeviceServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port, events=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.lock = threading.Lock()
        self.events = events
        self.state = {"rgb": [0, 0, 0], "brightness": 128, "text": "", "counter": 0}

    def dispatch(self, request):
        with self.lock:
            if self.events:
                with self.events.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(request, ensure_ascii=False) + "\n")
            command = request.get("cmd")
            error = None
            if command == "color":
                rgb = [request.get(key) for key in ("r", "g", "b")]
                if any(type(value) is not int or not 0 <= value <= 255 for value in rgb):
                    error = ("E_ARG", "RGB 必须是 0–255 的整数")
                else:
                    self.state["rgb"] = rgb
            elif command == "brightness":
                value = request.get("value")
                if type(value) is not int or not 0 <= value <= 255:
                    error = ("E_ARG", "亮度必须是 0–255 的整数")
                else:
                    self.state["brightness"] = value
            elif command == "text":
                value = request.get("value")
                if not isinstance(value, str) or len(value) > 256:
                    error = ("E_ARG", "文字必须是 256 字以内的字符串")
                else:
                    self.state["text"] = value
            elif command in ("increment", "delayed_increment"):
                amount = request.get("amount", 1)
                if type(amount) is not int or not 1 <= amount <= 10:
                    error = ("E_ARG", "增量必须是 1–10 的整数")
                else:
                    self.state["counter"] += amount
            elif command == "fail":
                error = ("E_HW", "模拟外设离线")
            elif command not in ("status", "malformed"):
                error = ("E_CMD", "模拟设备不支持此命令")
            response = {"id": request.get("id"), "ok": not error, "simulation": True}
            if error:
                response.update(code=error[0], error=error[1])
            else:
                response.update(self.state)
            return response


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            while line := self.rfile.readline(MAX_LINE + 1):
                if len(line) > MAX_LINE or not line.endswith(b"\n"):
                    return
                try:
                    request = json.loads(line.decode("utf-8"))
                    if not isinstance(request, dict):
                        raise ValueError("request must be an object")
                except (ValueError, UnicodeError):
                    self.connection.sendall(b'{"ok":false,"simulation":true,"code":"E_JSON"}\n')
                    continue
                response = self.server.dispatch(request)
                if request.get("cmd") == "delayed_increment" and response["ok"]:
                    time.sleep(5)  # Apply once, then delay the acknowledgement.
                if request.get("cmd") == "malformed":
                    self.connection.sendall(b"not-json\n")
                    continue
                wire = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
                # Force streaming behavior, including UTF-8 characters across packets.
                for offset in range(0, len(wire), 11):
                    self.connection.sendall(wire[offset:offset + 11])
        except (OSError, TimeoutError):
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--events", type=Path)
    options = parser.parse_args()
    if not 0 <= options.port <= 65535:
        parser.error("port must be 0–65535 (0 selects a free port)")
    with DeviceServer(options.port, options.events) as server:
        ready = {"host": "127.0.0.1", "port": server.server_address[1], "simulation": True}
        if options.ready_file:
            options.ready_file.parent.mkdir(parents=True, exist_ok=True)
            options.ready_file.write_text(json.dumps(ready), encoding="utf-8")
        print(json.dumps(ready), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
