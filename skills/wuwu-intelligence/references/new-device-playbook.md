# 新设备接入手册

用户说"我买了个 XX 模块/板子,帮我接上并控制"时走这里。目标:**问一轮,然后自己干到底**,只在必须用户动手(接线)或必须用户看实物时才停。

## 阶段 1:一轮问卷(必做,只问一次)

优先用 AskUserQuestion 工具出选择题,没有就用编号列表。最多 4 题,能从上下文推断的题不问,从流程 E 过来的题不重复问。

| 题 | 形式 | 选项示例 |
|---|---|---|
| 这是什么设备? | 填空 | 型号 / 商品链接 / 拍芯片丝印 |
| 想实现什么效果? | 选择 + 其他 | 手机电脑一句话控制 / 定时自动 / 跟随传感器联动 / 先点亮再说 |
| 用什么方式控制? | 选择 | WiFi(推荐) / USB 串口 / 蓝牙 / 不确定你定 |
| 主控和材料 | 多选 | ESP32-S3 / 其他 ESP32 / Arduino / 树莓派 / 有杜邦线 / 有独立电源 / 有面包板 |

## 阶段 2:知识判定(自主完成)

```
认识这个模块(常见传感器/舵机/屏幕/灯带)?
├─ 是 → 直接进阶段 3
└─ 否 → 联网搜「型号 + datasheet / arduino library / pinout」
    ├─ 找到资料 → 进阶段 3
    └─ 没找到 → 问用户一句"有没有说明书或购买页链接",同时自己开始探测:
        1. 数引脚、看丝印猜接口(VCC/GND/SDA/SCL=I2C,TX/RX=UART,DIN=单线,SIG/PWM=PWM)
        2. I2C 扫描 → 有地址就按地址查芯片
        3. UART 依次试 9600/115200/57600 看有无可读输出
        4. 数字引脚逐个拉高看有无反应(仅限已确认 3.3V 安全的模块)
        连续三种方案都失败 → 向用户报告,附上"已排除清单",问是否换思路
```

## 阶段 3:选工具链(自主完成,记进 hardware.toolchain)

不预设任何一种,按下面顺序定:

1. **用户有明确偏好**(问卷里说了、或用户级 CLAUDE.md 配了某套环境)→ 用它
2. **已有项目目录** → 看文件判断:`platformio.ini` → PlatformIO;`CMakeLists.txt` + `sdkconfig` → ESP-IDF;`*.ino` → Arduino;`boot.py`/`main.py` → MicroPython / CircuitPython;树莓派上的 `.py` → Linux Python
3. **全新项目** → 按需求选,理由一句话告诉用户:

| 场景 | 优先 | 原因 |
|---|---|---|
| ESP32 系列 + 常见模块,想快 | Arduino(有现成库)或 PlatformIO(同库,命令行更好自动化) | 库最全 |
| ESP32 系列,要精细控制 / 低功耗 / 摄像头 / 用户本机已装 IDF | ESP-IDF | 官方、功能全 |
| 想改代码不用重新编译 / 教学 | MicroPython | 改完即跑 |
| RP2040 / 部分 nRF 板 | CircuitPython 或 Arduino | 官方支持好 |
| 树莓派 / Linux 板 | Python + gpiozero / smbus2 | 不用固件 |
| 其他板子 | 查该板官方推荐 | 别硬套 |

4. 先确认该工具链本机能用(`arduino-cli version` / `idf.py --version` / `pio --version` / `mpremote version`),不能用就装或换,**不要卡住问用户**

## 阶段 4:接线方案(唯一必须等用户的点)

1. **先说安全提醒**(每次让用户动线都说,不省略):
   - 先断电再动线,接完再上电
   - 所有电源必须共地
   - 电机/舵机/大灯带(>500mA)必须独立供电,感性负载加续流二极管
   - 3.3V 模块别接 5V;涉及市电的部分找有经验的人
2. 画 ASCII 接线图,标电源来源和共地
3. GPIO 选择规则(ESP32-S3):避开 strapping(0/3/45/46)、USB(19/20)、Flash/PSRAM(26~37);推荐 38~42/47/48。其他板子查官方 pinout
4. 结尾一句:"接好后拍张照给我或回一句'接好了'"

## 阶段 5:固件开发(自主)

- 套 protocol-template.md 骨架:单行 JSON + 统一错误码 + 非阻塞状态机;transport 按问卷选 tcp / serial / ble
- 目录按工具链惯例:Arduino `<name>/firmware/<name>/<name>.ino`;ESP-IDF `<name>/firmware/main/`;PlatformIO `<name>/firmware/src/`;MicroPython `<name>/firmware/main.py`
- 顶部(或 `config.h` / `sdkconfig` / `config.py`)用户配置区:WIFI / PIN / 端口集中放置,WiFi 密码只放这里
- 每个功能一个 cmd,外加 status 查询;串口日志用统一前缀 `[wifi]` `[tcp]` `[ble]` `[hw]`

## 阶段 6:编译烧录(自主,见 SKILL.md 流程 D)

- 按 hardware.toolchain 用对应命令;串口自动检测,只有多个口时才让用户选
- 烧录前一句话告知,不等确认;烧录后自己读串口日志确认(`[wifi] status=3 ip=...` / `[tcp] server started`)
- 编译报错看第一段红字;烧录卡 Connecting 让用户按住 BOOT

## 阶段 7:PC 端封装(自主)

- `<name>/pc/<name>_dev.py` 通信库(按 transport 选 socket / pyserial / bleak)+ `<name>_cli.py` 命令行
- 每个固件 cmd 一个方法 / 子命令;`--ip` / `--port` 自动记忆到 `pc/device.json`;错误码翻译成中文
- 加一个 `demo.py` 把所有功能串一遍

## 阶段 8:自测 + 让用户看一眼

- 自己逐条跑:连通 → 基础控制 → 高级功能 → status → 故意传错参数(应返回 E_ARG)
- 只问用户一句实物效果("舵机转了吗?"),不让用户跑命令

## 阶段 9:登记 + 交付(必做)

1. 写入 devices.json 的 `devices` 数组:name / aliases(含中文口语)/ project_path / control(含 transport)/ **global_options(CLI 所有公共参数,如 --ip / --port / --forget / --timeout)** / **commands(每条指令一个对象:desc 一句话说做什么、run 命令模板、args 每个占位符的含义 + 范围 + 默认值)** / hardware(mcu、toolchain、引脚、flash_port、power)/ manual
   - 检验标准:一个没看过代码的人只读这份档案就能正确敲出每条命令。做不到就补全
2. 按 delivery-doc-guide.md 用 `references/manual-template.html` 生成 `<project_path>/docs/manual.html`,生成后自动用浏览器打开
3. 最后告诉用户:以后直接说"XX 设成 YY"就行,说明书在哪
