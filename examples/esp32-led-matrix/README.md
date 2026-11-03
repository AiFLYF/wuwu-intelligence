# ESP32-S3 + WS2812B-64 灯板示例（骨架）

> **验证状态：未在真实硬件上验证。**
> 本目录是按 [protocol-template](../../skills/wuwu-intelligence/references/protocol-template.md)
> 与 [troubleshooting](../../skills/wuwu-intelligence/references/troubleshooting.md) 整理的
> 最小骨架，目的是给「接入新设备」流程一个可照抄的起点。固件与 CLI 尚未在任何实体
> 灯板上编译、烧录或运行过；第一次使用前请按
> [new-device-playbook](../../skills/wuwu-intelligence/references/new-device-playbook.md)
> 走完接线核对与逐步实测，再把验证结论回填到这里。

## 材料

| 项 | 规格 |
|---|---|
| 主控 | ESP32-S3 开发板（USB 供电即可开发） |
| 灯板 | WS2812B 8×8 全彩矩阵（64 珠） |
| 电源 | 独立 5V ≥ 4A（64 珠满载约 3.8A，不要从板载 5V 取电） |
| 其他 | 330Ω 电阻 ×1、1000µF 电容 ×1、杜邦线 |

## 接线

```text
                 ESP32-S3                     WS2812B-64
               ┌───────────┐                ┌────────────┐
   USB(开发)──>│           │  GPIO38 ─[330Ω]─>│ DIN        │
               │           │        │       │            │
   独立 5V≥4A ────────────┼────────┼───────>│ 5V         │
      (接灯板)  │           │        │       │            │
               │       GND ├────────┴───────│ GND        │
               └───────────┘   必须共地      └────────────┘
                                  灯板 5V/GND 入口并 1000µF 电容
```

先断电再接线，接完拍照核对再上电。灯板必须独立供电，ESP32 与灯板共地。

## 锁定的工具链版本

撰写时的已知良好组合（未在本示例验证，版本号请在安装时核对仍存在）：

```bash
arduino-cli core install esp32:esp32@2.3.4
arduino-cli lib install "FastLED@3.7.8" "ArduinoJson@7.2.0"
# 开发板 FQBN：esp32:esp32:esp32s3；Partition Scheme 选 Huge APP (3MB)
```

编译烧录：

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/led_matrix
arduino-cli upload  --fqbn esp32:esp32:esp32s3 --port <串口> firmware/led_matrix
arduino-cli monitor --port <串口> --config baudrate=115200   # 看分配到的 IP
```

固件顶部的 `WIFI_SSID` / `WIFI_PASS` 需要改成你的网络；这两个值属于本地凭据，
不要提交（生产做法是把它们挪进被 .gitignore 排除的 `config.h`）。

## 命令与协议

TCP 长连接，ESP32 为服务器（端口 8888），单行 JSON 一问一答：

| 命令 | 示例 | 说明 |
|---|---|---|
| `color` | `{"cmd":"color","r":255,"g":0,"b":0}` | 整板纯色 |
| `brightness` | `{"cmd":"brightness","value":120}` | 0–255 |
| `off` | `{"cmd":"off"}` | 熄灭 |
| `status` | `{"cmd":"status"}` | 只读：颜色/亮度/IP/RSSI |

PC 端调用（标准库，无第三方依赖）：

```bash
python pc/led_cli.py --ip 192.168.1.50 status
python pc/led_cli.py --ip 192.168.1.50 color 255 0 0
python pc/led_cli.py --ip 192.168.1.50 brightness 120
python pc/led_cli.py --ip 192.168.1.50 off
```

`--ip` 成功一次后写入 `pc/device.json`（本目录已被仓库忽略规则覆盖，
请确认你自己的项目也忽略它），之后可省略。

## 登记到万物智能

把 `devices.example.json` 复制为独立文件、替换 `project_path` 为真实绝对路径后：

```bash
python skills/wuwu-intelligence/scripts/device_registry.py register --file <你的文件> --dry-run
python skills/wuwu-intelligence/scripts/device_registry.py register --file <你的文件>
```

## 目录

```text
firmware/led_matrix/led_matrix.ino   最小固件（WiFi + TCP + 单帧非阻塞 loop）
pc/led_cli.py                        标准库 TCP CLI
devices.example.json                 注册表登记描述（单台设备对象，不是整份注册表）
```
