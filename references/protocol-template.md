# 通用通信协议骨架(TCP + 单行JSON + 非阻塞)

新设备固件直接套这个模式,已验证稳定。参考实现源自 RGB_ding(ESP32-S3 + WS2812B-64 灯板)项目,未随本仓库发布,按下方要点实现即可。

## 协议设计规则

1. **传输**:TCP 长连接,ESP32 为服务器,端口写进配置区(默认8888)
2. **指令**:单行 JSON + '\n' 结尾,必有 "cmd" 字段区分指令
3. **响应**:单行JSON + '\n';成功 {"ok":true,...},失败 {"ok":false,"error":"中文或英文短句"}
4. **一条指令恰好一个响应**(客户端按行等响应,多发漏发都会卡)
5. 参数缺失时给合理默认值(doc["speed"] | 20),别报错

## 固件骨架要点(ESP32 Arduino)

```
loop() {
  ensureWiFi();      // 掉线每12s强制 disconnect->begin 重连
  handleClients();   // 读TCP缓冲,凑齐一行 -> processLine()
  updateAnimation(); // millis()节拍推进动画帧,非阻塞关键
  delay(1);
}
```

- setup():WiFi.mode(WIFI_STA) + setSleep(false) + setAutoReconnect(true)
- 首连重试8轮×10s(热点beacon/DHCP慢很常见)
- processLine():ArduinoJson v7 JsonDocument 解析 → strcmp 分发 → 每分支恰一次 sendResponse
- 命令函数返回 const char* 错误串(nullptr=成功),由分发处统一发响应,避免双发/漏发
- status 类查询指令返回当前模式/关键参数/IP/RSSI,方便上位机验证

## PC端骨架要点(Python 标准库)

```
class XxxDevice:
    __enter__/__exit__/connect/close     # with语法管理连接
    _send(dict)->dict                    # 发送+按行收响应,ok!=True抛XxxError
    _recv_line()                         # 缓冲区处理粘包/多行
    # 下面每个固件cmd对应一个语义化方法
```

CLI:argparse子命令;--ip 成功一次后存 json 自动记住;--forget 清除;连接失败打印中文排查提示。

## 扩展新指令三步法

固件 processLine 加分支 → Python库加方法(self._send({...})) → CLI加子命令。
改固件必须重新编译烧录;PC端跑 python -m py_compile 验证。
