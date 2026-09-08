# wuwu-intelligence 万物智能

> 对接并控制任意硬件设备的通用工作流 · Universal workflow for connecting and controlling any hardware device.

一个面向小白的 Claude Code 技能（Skill）：用自然语言控制已注册的硬件、接入全新硬件、为已有设备扩展新功能。全程中文友好，执行前说明意图，结果用人话汇报。

A Claude Code Skill that lets you control registered hardware in plain language, onboard new devices, and extend existing ones. Chinese-friendly, explains before acting.

---

## ✨ 特性 Features

- **控制已有设备** — 读 `devices.json` 注册表，按口语别名匹配设备，自动取 IP 并执行
- **接入全新设备** — 六阶段流程：确认目标 → 接线方案 → 固件开发 → 编译烧录 → PC 端封装 → 测试+登记
- **扩展已有设备** — 三步法：固件加 `cmd` 分支 → Python 库加方法 → CLI 加子命令
- **排障决策树** — WiFi / 供电共地 / 编译烧录 / 动画卡顿等真实踩坑沉淀
- **通信协议模板** — TCP + 单行 JSON + 非阻塞状态机，可直接套用

## 📁 目录结构 Structure

```
wuwu-intelligence/
├── SKILL.md              # 技能主文件（触发条件 + 四条工作流 + 小白守则）
├── devices.json.example  # 设备注册表模板（复制为 devices.json 后按你的设备填写）
├── references/
│   ├── new-device-playbook.md   # 新设备接入手册（六阶段）
│   ├── protocol-template.md     # 通信协议骨架
│   ├── extension-guide.md       # 扩展已有设备三步法
│   └── troubleshooting.md       # 排障决策树
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
或直接说「灯板设成红色」——如果设备已登记，技能会读 `devices.json` 开始工作；如果还没登记设备，它会列出模板并引导你填写。

### 🤖 让 Agent 自动安装

把下面这句话发给任意 Claude Code 会话，agent 会照 README 完成全部步骤：

```
请安装 https://github.com/AiFLYF/wuwu-intelligence 这个 Claude Code 技能：克隆到 ~/.claude/skills/wuwu-intelligence，把 devices.json.example 复制为 devices.json，然后告诉我怎么验证。
```

> agent 执行时的自检清单：① 确认 `~/.claude/skills/wuwu-intelligence/SKILL.md` 存在且 frontmatter 含 `name: wuwu-intelligence`；② `devices.json` 不存在时从 `devices.json.example` 复制，**已存在则不要覆盖**（里面有用户自己的设备数据）；③ 完成后提醒用户：新开会话后技能才生效。

## 🗣️ 使用示例 Usage

```
“帮我把灯板全部设置为红色”
“演示一下灯板 demo”
“灯连不上了”
“我买了个舵机，帮我接上并控制”
“给灯板加个显示文字的功能”
```

技能会：
1. 读 `devices.json` 找到对应设备
2. 取 IP（从设备项目中 `device.json` 自动记住的地址）
3. 执行对应命令/脚本并验证结果
4. 用中文汇报结果，失败则走排障流程

## 📝 注册自己的设备

复制 `devices.json.example` 为 `devices.json`（本地文件，不入库），按模板新增一条：

> 模板里的示例设备 RGB_ding（ESP32-S3 + WS2812B-64 灯板）**不随本仓库发布**，示例条目仅演示格式，请替换为你自己的项目路径和命令。

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
  "hardware": {
    "mcu": "ESP32-S3",
    "signal_pin": "GPIO38"
  },
  "quick_examples": {
    "示例": "python pc/cli.py <cmd>"
  }
}
```

## 📖 参考文档 References

- [新设备接入手册](references/new-device-playbook.md)
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
