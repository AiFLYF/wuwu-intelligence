# 排障决策树(来自真实踩坑,持续补充)

**只在命令真的失败后才读本文。** 读之前应已自动做过:跑 status 复现、重试一次、ping 设备 IP、能开串口就读一段日志。先自己顺着树往下排,能自己确认的(ping、端口、串口输出)自己确认,只把需要用户动手 / 看实物的那一步说出来。

## 0. 先看设备返回的错误码(有响应说明链路是通的)
| code | 跳到 |
|---|---|
| `E_CMD` | 设备没这个功能 → 建议走流程 C 扩展,不是故障 |
| `E_ARG` | 参数错 → 对照 devices.json 的 args 重填 |
| `E_BUSY` | 等 1 秒重试;反复出现 → 固件某动作没收尾,查非阻塞状态机 |
| `E_HW` | 外设无响应 → 第 3 节(接线 / 供电) |
| `E_TIMEOUT` | 重试一次;仍失败 → 重启设备,再看第 6 节 |
| 连接层报错(timeout / refused / 串口打不开) | 第 1 节 |

## 1. PC 连不上设备
### 1a. TCP(timeout / refused)
```
ping 设备IP 通吗?
├─ 不通 → 设备离线或IP变了
│   ├─ 问用户:设备通电吗?板载电源灯亮吗?
│   ├─ 让用户看串口监视器(115200)打印的 [wifi] ip=...
│   ├─ 路由器可能重新分配了IP → 用新IP重试(成功后CLI会自动记住)
│   └─ 手机热点场景:热点可能"半睡",开关一次热点;固件已带8轮重试+12s强制重连
└─ 通 → 端口问题:防火墙拦8888?设备TCP server起了吗?(串口应有 "[tcp] server started")
```
### 1b. 串口(打不开 / 无响应)
- 打不开:COM 号变了(拔插 USB 看设备管理器)、被串口监视器 / 另一个程序占着
- 打开但无响应:波特率不对(应与固件一致,默认 115200)、固件没起来(按 RST)、行尾不是 `\n`
### 1c. BLE(扫不到 / 连不上)
- 扫不到:设备没在广播(串口应有 "[ble] advertising")、已被手机连着(BLE 一对一)
- 连上就断:PC 蓝牙驱动老、距离远;先在设备旁边试

## 2. WiFi 连不上(status码诊断,串口可见)
- status=1 找不到SSID:SSID错/路由器没开2.4G(ESP32不支持5G)/信号太弱
- status=4 认证失败:密码错;路由器WPA3-only兼容差→改WPA2或混合
- status=6 断开:常见于手机热点休眠;固件需有强制重连逻辑(disconnect->begin,别只调reconnect)
- 首连失败但配置正确:热点beacon/DHCP慢,多轮重试(8轮×10s)能自愈

## 3. 灯不亮/乱闪/颜色不对
- 完全不亮:查5V/GND是否接对、IN线是否接到配置的GPIO
- 乱闪:90%是**没共地**;其次IN线过长无330Ω电阻、电源纹波(并1000µF电容)
- 亮度低时正常、高时闪:供电不足(64珠满载~3.8A,需独立5V≥4A)
- 颜色红绿对调:改 FastLED addLeds<...> 的色彩顺序(GRB/RGB)
- 图案方向反了/镜像:切 LAYOUT_ZIGZAG(true=蛇形,false=逐行)

## 4. 编译错误(先看第一段红色错误,后面全是连锁)
- Arduino:'JsonDocument' not found → ArduinoJson 版本<7,升级;FastLED 相关 → 库管理器更新;确认开发板选 ESP32S3 Dev Module;Flash 溢出(>96%) → Partition Scheme→Huge APP (3MB)
- ESP-IDF:先 `export.bat` 再 `idf.py`;改过 sdkconfig 报怪错 → `idf.py fullclean`;target 不对 → `idf.py set-target esp32s3`
- PlatformIO:库找不到 → `lib_deps` 写全;板子名错 → 查 `pio boards`
- MicroPython:ImportError → 该固件没编进这个模块,换 build 或用纯 Python 实现

## 5. 烧录失败
- "Connecting........_____" 卡住:按住板上 BOOT 键不放再点上传
- 没有 COM 口:换 USB 线(有的线只能充电)、装 CP210x/CH34x 驱动
- 上传后无输出:串口监视器波特率 115200?按 RST 复位
- MicroPython `mpremote` 连不上:REPL 被别的串口程序占着

## 6. 动画卡顿/指令无响应
- 固件里有没有 delay() 卡主循环(应全部millis非阻塞)
- FastLED.show() 频率过高占CPU;帧间隔建议≥20ms
