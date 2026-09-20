# wuwu-intelligence 万物智能

> 对接并控制任意硬件设备的通用工作流 · Universal workflow for connecting and controlling any hardware device.

一个面向小白的 Claude Code 技能（Skill）：用自然语言控制已注册的硬件、接入全新硬件、为已有设备扩展新功能。全程中文友好，执行前说明意图，结果用人话汇报。

A Claude Code Skill that lets you control registered hardware in plain language, onboard new devices, and extend existing ones. Chinese-friendly, explains before acting.

> 🖥️ **项目介绍页 → https://aiflyf.github.io/wuwu-intelligence/**
>
> 源码在 [`docs/`](docs/index.html)，含一块实时渲染的 8×8 WS2812B 灯板
> （three.js，7 套效果可切换）、五条工作流的可视化说明，以及「手动安装 / 让 Agent 自动装 / 验证与生效」
> 三种安装方式。样式、脚本、字体、three.js **全部本地化，离线可跑**。
>
> ```bash
> # 本地预览（用了 ES module，必须走 HTTP，直接双击打开会被浏览器的 CORS 策略拦住）
> cd docs && python -m http.server 8080
> # 然后打开 http://localhost:8080
> ```
>
> 已经部署在 GitHub Pages（`main` 分支的 `/docs` 目录）；换仓库或换分支时：
> Settings → Pages → Source 选 `Deploy from a branch`，目录选 `/docs`。

---

## ✨ 特性 Features

- **控制已有设备（快路径）** — 只读 `devices.json` 一个文件，按口语匹配 `commands` 立刻执行；不读源码、不预先 ping、不问「确认吗」；失败才自动重试 + 排障
- **接入全新设备** — 一轮选择题问清需求 → 认识的模块直接干，不认识就联网搜或自己探测排除 → 按项目和需求自动选工具链（Arduino / PlatformIO / ESP-IDF / MicroPython / 树莓派 Python 等，不预设）→ 接线（唯一等你的一步）→ 固件/烧录/PC 端全自主 → 登记 + 交付说明书
- **创意工坊** — 「我有几个模块不知道做什么」→ 几道选择题 → 给 2-3 个方案（效果/用到什么/还缺什么/难度）→ 你选一个就开干
- **扩展已有设备** — 三步法：固件加 `cmd` 分支 → Python 库加方法 → CLI 加子命令，完成后同步更新说明书
- **HTML 交付说明书** — 单文件模板，填占位符、换主题色即成；three.js 3D 头图（离线自动降级），含「你可以这样说」指令表、错误码表、常见问题、安全须知
- **排障决策树** — 先自动复现 + ping + 读日志，再按错误码 / WiFi 状态码 / 供电共地 / 编译烧录分支排查，真实踩坑沉淀
- **通信协议模板** — 单行 JSON + 统一错误码（E_CMD / E_ARG / E_BUSY / E_HW / E_TIMEOUT）+ 非阻塞状态机，WiFi TCP / USB 串口 / BLE 三种传输可选

## 📁 目录结构 Structure

```
wuwu-intelligence/
├── SKILL.md              # 技能主文件（触发条件 + 五条工作流 + 小白守则）
├── devices.json.example  # 设备注册表模板（复制为 devices.json 后按你的设备填写）
├── references/
│   ├── new-device-playbook.md   # 新设备接入手册（一轮问卷 → 自主推进 → 交付）
│   ├── idea-workshop.md         # 创意工坊（有模块不知道做什么）
│   ├── delivery-doc-guide.md    # HTML 说明书生成指南
│   ├── manual-template.html     # 说明书模板（填占位符 + 换主题色即可）
│   ├── protocol-template.md     # 通信协议骨架（统一错误码，tcp / serial / ble）
│   ├── extension-guide.md       # 扩展已有设备三步法
│   └── troubleshooting.md       # 排障决策树
├── docs/                        # 项目介绍页（与技能运行无关，纯展示）
│   ├── index.html               # 单页介绍页，浏览器直接打开
│   └── assets/                  # 样式 / 脚本 / 字体 / three.js，全部本地，离线可跑
└── README.md
```

## 🚀 安装 Installation

> 仓库地址：https://github.com/AiFLYF/wuwu-intelligence

### 手动安装（两条命令）

```bash
# 1. 克隆到用户级 skills 目录（Claude Code 会自动发现）
#    Windows 下 ~ 即 C:\Users\<你的用户名>
git clone --depth 1 https://github.com/AiFLYF/wuwu-intelligence.git \
  ~/.claude/skills/wuwu-intelligence

# 2. 复制设备注册表模板（本地文件，已被 .gitignore 排除）
cp ~/.claude/skills/wuwu-intelligence/devices.json.example \
   ~/.claude/skills/wuwu-intelligence/devices.json
```

- 也可以克隆到某个项目的 `.claude/skills/` 下，仅在该项目内生效
- 已安装过？进目录 `git pull` 更新即可
- **生效方式**：技能在会话启动时加载——安装后**新开一个 Claude Code 会话**才会生效

### 验证安装

新会话里问一句：「你现在加载了哪些技能？有没有万物智能？」
或直接说「灯板设成红色」——如果设备已登记，技能会读 `devices.json` 直接执行；如果还没登记设备，它会告诉你注册表是空的，并问你是要接入新设备还是手动填写。

### 🤖 让 Agent 自动安装

把下面这句话发给任意 Claude Code 会话，agent 会照 README 完成全部步骤：

```
请安装 https://github.com/AiFLYF/wuwu-intelligence 这个 Claude Code 技能：克隆到 ~/.claude/skills/wuwu-intelligence，把 devices.json.example 复制为 devices.json，然后告诉我怎么验证。
```

> agent 执行时的自检清单：① 确认 `~/.claude/skills/wuwu-intelligence/SKILL.md` 存在且 frontmatter 含 `name: wuwu-intelligence`；② `devices.json` 不存在时从 `devices.json.example` 复制，**已存在则不要覆盖**（里面有用户自己的设备数据）；③ 完成后提醒用户：新开会话后技能才生效。

## 🗣️ 使用示例 Usage

```
"帮我把灯板全部设置为红色"        → 直接执行，一句话汇报
"跑个 demo"                       → 直接执行
"灯连不上了"                      → 自动重试 + ping，再用人话告诉你原因
"我买了个舵机，帮我接上并控制"    → 几道选择题 → 自主接入 → 说明书
"我有个温湿度模块和灯带，能做啥"  → 给你 2-3 个方案选
"给灯板加个显示文字的功能"        → 三步法扩展 + 更新说明书
"打开灯板说明书"                  → 打开 HTML 说明书
```

控制类指令的原则：**从你开口到命令跑起来，中间只读 `devices.json` 一个文件**。不读源码、不预先检查连接、不问确认。失败了才自动重试一次、ping 一下，然后走排障树。

## 📝 注册自己的设备

复制 `devices.json.example` 为 `devices.json`（本地文件，不入库）。初始 `devices` 数组为空，`_template` 只是格式示范，**技能不会把它当成真实设备**。新增一条到 `devices` 里：

```json
{
  "name": "my_device",
  "aliases": ["别名1", "别名2"],
  "description": "一句话描述",
  "project_path": "/path/to/your/project",
  "control": {
    "cli": "pc/cli.py",
    "lib": "pc/device_lib.py",
    "transport": "tcp:8888",
    "ip_lookup": "pc/device.json"
  },
  "global_options": {
    "--ip <地址>": "指定设备 IP，成功一次后自动记住",
    "--forget": "清除记住的 IP"
  },
  "commands": {
    "color": {
      "desc": "全部灯珠设为同一颜色；关灯就是 0 0 0",
      "run": "python pc/cli.py color {r} {g} {b}",
      "args": {"r": "红 0-255", "g": "绿 0-255", "b": "蓝 0-255"}
    },
    "demo": {
      "desc": "依次展示所有效果",
      "run": "python pc/demo.py"
    }
  },
  "hardware": {
    "mcu": "ESP32-S3",
    "toolchain": "arduino",
    "signal_pin": "GPIO38",
    "flash_port": "COM7",
    "power": "独立5V，与主控共地"
  },
  "manual": "docs/manual.html"
}
```

`commands` 是快路径的核心，相当于把 `--help` 写进注册表：`desc` 一句话说这条命令做什么（技能靠它理解你的口语，不用穷举说法），`run` 是真实命令模板，`args` 写清每个占位符的含义、范围和默认值；`global_options` 列出所有子命令通用的可选参数。写全之后技能**只读这一个文件就能控制设备**，不跑 `--help`、不读代码。检验标准：一个没看过代码的人只读这份档案就能正确敲出每条命令。通过技能接入的设备会自动写好这一段。

## 📖 参考文档 References

- [新设备接入手册](references/new-device-playbook.md)
- [创意工坊](references/idea-workshop.md)
- [HTML 说明书生成指南](references/delivery-doc-guide.md) · [说明书模板](references/manual-template.html)
- [通信协议模板](references/protocol-template.md)
- [扩展指南](references/extension-guide.md)
- [排障决策树](references/troubleshooting.md)

## 🔒 隐私 Privacy

- WiFi 密码等敏感信息不写入本技能任何文件，仅在你的本地项目固件配置区保存
- `devices.json` 中的示例 IP / 路径均为占位符，请替换为你自己的

## 📄 License

MIT — 详见 [LICENSE](LICENSE)。

## 🌱 起源 Origin

沉淀自 RGB_ding（ESP32-S3 + WS2812B-64）项目，首个验证设备为 8×8 全彩 LED 矩阵。
