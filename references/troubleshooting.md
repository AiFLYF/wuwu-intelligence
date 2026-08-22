# 排障决策树(来自真实踩坑,持续补充)

## 1. PC连不上设备(TCP timeout / refused)
```
ping 设备IP 通吗?
├─ 不通 → 设备离线或IP变了
│   ├─ 问用户:设备通电吗?板载电源灯亮吗?
│   ├─ 让用户看串口监视器(115200)打印的当前IP
│   ├─ 路由器可能重新分配了IP → 用新IP重试(成功后CLI会自动记住)
│   └─ 手机热点场景:热点可能"半睡",开关一次热点;固件已带8轮重试+12s强制重连
└─ 通 → 端口问题:防火墙拦8888?设备TCP server起了吗?(串口应有 "TCP server started")
```

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

## 4. 编译错误
- 第一段红色错误才是根因,后面全是连锁
- 'JsonDocument' not found → ArduinoJson 版本<7,升级
- FastLED相关 → 库管理器更新FastLED;确认开发板选 ESP32S3 Dev Module
- Flash溢出(>96%) → Tools→Partition Scheme→Huge APP (3MB)

## 5. 烧录失败
- "Connecting........_____" 卡住:按住板上BOOT键不放再点上传
- 没有COM口:换USB线(有的线只能充电)、装CP210x/CH34x驱动
- 上传后无输出:串口监视器波特率115200?按RST复位

## 6. 动画卡顿/指令无响应
- 固件里有没有 delay() 卡主循环(应全部millis非阻塞)
- FastLED.show() 频率过高占CPU;帧间隔建议≥20ms
