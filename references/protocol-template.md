# 通用通信协议骨架(单行 JSON + 非阻塞状态机)

新设备固件直接套这个模式,已验证稳定。参考实现源自 RGB_ding(ESP32-S3 + WS2812B-64 灯板)项目,未随本仓库发布,按下方要点实现即可。

## 协议设计规则(与传输方式无关)

1. **指令**:单行 JSON + `\n` 结尾,必有 `"cmd"` 字段区分指令
2. **响应**:单行 JSON + `\n`;成功 `{"ok":true,...}`,失败 `{"ok":false,"code":"E_ARG","error":"中文短句"}`
3. **一条指令恰好一个响应**(客户端按行等响应,多发漏发都会卡)
4. 参数缺失时给合理默认值(`doc["speed"] | 20`),别报错
5. `status` 查询必有:当前模式 / 关键参数 / 连接信息(IP+RSSI 或串口号)/ 运行秒数,方便上位机验证

## 统一错误码(固件、Python 库、说明书三处一致)

| code | 含义 | 上位机应该怎么做 |
|---|---|---|
| `E_CMD` | 未知指令 | 提示"设备不支持这个功能",建议走扩展流程 |
| `E_ARG` | 参数缺失 / 越界 / 类型错 | 按 devices.json 的 args 说明重填 |
| `E_BUSY` | 设备忙(上一个动作未完成) | 等 1 秒重试一次 |
| `E_HW` | 硬件故障(传感器无响应、外设初始化失败) | 走排障树第 3 节(接线 / 供电) |
| `E_TIMEOUT` | 固件内部等待超时 | 重试一次,仍失败走排障 |
| `E_JSON` | 收到的不是合法 JSON | 库自身 bug,报给用户 |

Python 库把 `code` 放进异常对象(`XxxError.code`),CLI 打印时按上表翻译成人话。

## 传输方式(三选一,transport 字段写法)

| 方式 | transport | 适用场景 | 固件侧 | PC 侧 |
|---|---|---|---|---|
| **WiFi TCP**(默认) | `tcp:8888` | 设备有 WiFi,想远程 / 多设备 | 设备作 TCP 服务器 | 标准库 `socket` |
| **USB 串口** | `serial:COM7@115200` | 没 WiFi、桌面固定使用、调试期 | `Serial.readStringUntil('\n')` | `pyserial` |
| **BLE** | `ble:<设备名>` | 手机控制、低功耗、没 WiFi | Nordic UART Service(NUS) | `bleak` |

同一固件可同时开 TCP + 串口(串口本来就要开做日志),按行分发到同一个 `processLine()`。

### 固件主循环骨架(Arduino 风格,其他工具链同思路)

```
loop() {
  ensureLink();      // TCP: 掉线每12s强制 disconnect->begin;串口/BLE: 无需
  handleInput();     // 读缓冲,凑齐一行 -> processLine(line, replyTo)
  updateAnimation(); // millis()节拍推进动画帧,非阻塞关键
  delay(1);
}
```

- WiFi:`WIFI_STA` + `setSleep(false)` + `setAutoReconnect(true)`;首连重试 8 轮 × 10s
- `processLine()`:ArduinoJson v7 `JsonDocument` 解析 → strcmp 分发 → 每分支恰一次 `sendResponse`
- 命令函数返回 `const char*` 错误码(`nullptr` = 成功),分发处统一发响应,避免双发 / 漏发
- 串口日志统一前缀方便上位机抓:`[wifi] status=3 ip=192.168.1.20` `[tcp] server started :8888` `[ble] advertising`

### PC 端骨架(Python)

```
class XxxDevice:
    __enter__/__exit__/connect/close     # with 语法管理连接
    _send(dict)->dict                    # 发送 + 按行收响应;ok!=True 抛 XxxError(code, msg)
    _recv_line()                         # 缓冲区处理粘包 / 多行
    # 每个固件 cmd 对应一个语义化方法
```

- transport 解析:`tcp:` → socket;`serial:` → pyserial;`ble:` → bleak(异步,包一层同步接口)
- CLI:argparse 子命令;`--ip` / `--port` 成功一次后存 `device.json` 自动记住;`--forget` 清除;连接失败打印中文排查提示

## 扩展新指令三步法

固件 processLine 加分支 → Python 库加方法(`self._send({...})`)→ CLI 加子命令。
改固件必须重新编译烧录;PC 端跑 `python -m py_compile` 验证。
