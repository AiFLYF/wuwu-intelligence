# 万物智能 · WuWu Intelligence

用自然语言控制已登记的硬件，让接入、扩展、排障和交付有一套可复用的流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-blueviolet.svg)](https://agentskills.io/specification)

**[体验交互 Demo](https://aiflyf.github.io/wuwu-intelligence/) · [快速开始](#快速开始) · [设备注册表](#设备注册表) · [开发与验证](#开发与验证)**

这是一个遵循 Agent Skills 标准的硬件工作流 Skill，包含设备注册表工具、接入与排障指南，以及 HTML 说明书模板。它依据已登记的命令调用设备项目的 CLI，协助你把「灯板设成红色」变成一次有依据的操作。

仓库提供工作流与命令调度工具，**设备固件、通信库和硬件 CLI 由具体项目提供**。首个实践来源是 RGB_ding（ESP32-S3 + WS2812B 8×8 灯板）项目；其他硬件需要按型号和接口接入。网页 Demo 是浏览器中的交互模拟，不会连接真实设备，也不调用模型 API。

An Agent Skill for registered-device control, hardware onboarding, troubleshooting, and delivery documentation. Device firmware and drivers are supplied by each hardware project.

## 快速开始

需要 Node.js LTS 与支持 Skills 的 Agent；本地注册表工具需要 Python 3.10+。

```bash
npx skills add AiFLYF/wuwu-intelligence --skill wuwu-intelligence
```

按安装器提示选择目标 Agent 和安装范围，完成后新开会话：

> 用万物智能检查我的设备档案，告诉我现在有哪些已登记设备。

首次使用会在 `~/.wuwu-intelligence/devices.json` 建立空档案，已有档案会保留；该目录独立于 Skill 安装位置。初次验证只检查档案，不发送设备动作。

接下来可以说：

| 你的需求 | 工作流 |
|---|---|
| 「灯板设成红色」 | 匹配已登记设备和命令，校验参数后执行 |
| 「买了一个温湿度模块，帮我接上」 | 确认型号和目标 → 选工具链 → 接线 → 开发与验证 → 登记 |
| 「给灯板加显示文字的功能」 | 更新需要改动的固件、库和 CLI，同步档案与说明书 |
| 「灯板连不上了」 | 先做只读诊断，再按实际通信方式排障 |
| 「手头这些模块能做什么」 | 给出材料、效果、难度和成本明确的方案 |
| 「打开灯板说明书」 | 打开登记的本地 HTML 文档 |

没有登记设备或没有对应命令时，Skill 会说明缺少的内容。示例文件中的 `_template` 不会被当成真实设备执行。

## 能力与执行方式

- **设备控制**：以 `devices.json` 为依据，减少反复读源码和查帮助；同名或别名冲突会报错，参数类型和范围在执行前校验。
- **新设备接入**：按用户需求和项目选择 Arduino、PlatformIO、ESP-IDF、MicroPython 等工具链；接线和硬件测试根据实际型号推进。
- **扩展与交付**：优先复用已有能力，需要新指令时同步修改固件、通信库、CLI、注册表和说明书。
- **可预览的命令调度**：`plan` 只输出计划；`run` 使用参数数组执行一次本地程序，不经 shell 拼接、不自动重试。
- **有边界的排障**：参数错误不原样重试；超时视为结果未知；只有确认可安全重复的命令才考虑一次重试，串口和 BLE 不做 IP ping。

## 安装

### 通过 Skills CLI 安装

推荐使用上面的安装命令，由安装器处理各 Agent 的目录差异。需要用户级安装并跳过安装器选择时：

```bash
npx skills add AiFLYF/wuwu-intelligence --skill wuwu-intelligence -g -y
```

也可以把下面这段发给 Agent：

> 请安装 https://github.com/AiFLYF/wuwu-intelligence 中的 wuwu-intelligence Skill。保留已有设备档案，检查 SKILL.md 和注册表工具是否安装成功，再告诉我如何在新会话中验证。

### 手动安装到 Claude Code

先克隆到普通工作目录。只复制仓库中的 `skills/wuwu-intelligence`，不要把整个仓库直接克隆为已安装 Skill 的目录。

```bash
git clone --depth 1 https://github.com/AiFLYF/wuwu-intelligence.git
```

Bash：

```bash
skill_target="$HOME/.claude/skills/wuwu-intelligence"
if [ -e "$skill_target" ]; then
  printf '%s\n' '目标已存在，请先备份设备档案并按升级说明处理。'
else
  mkdir -p "$HOME/.claude/skills"
  cp -R wuwu-intelligence/skills/wuwu-intelligence "$skill_target"
  python "$skill_target/scripts/device_registry.py" init
fi
```

Windows PowerShell：

```powershell
$skillTarget = Join-Path $HOME '.claude\skills\wuwu-intelligence'
if (Test-Path -LiteralPath $skillTarget) {
    throw '目标已存在，请先备份设备档案并按升级说明处理。'
}
New-Item -ItemType Directory -Force -Path (Split-Path $skillTarget) | Out-Null
Copy-Item -LiteralPath '.\wuwu-intelligence\skills\wuwu-intelligence' -Destination $skillTarget -Recurse
python (Join-Path $skillTarget 'scripts\device_registry.py') init
```

仅供某个项目使用时，安装到该项目的 `.claude/skills/`。其他 Agent 的路径由 Skills CLI 处理。

### Claude Code 插件方式

```text
/plugin marketplace add AiFLYF/wuwu-intelligence
/plugin install wuwu-intelligence@aiflyf-skills
```

### 升级与迁移

1. 新版默认把档案保存在 `~/.wuwu-intelligence/devices.json`，重复安装 Skill 不会删除该文件。也可通过 `WUWU_DEVICES_FILE` 或 `--registry` 指定独立路径。
2. 旧版若把 `devices.json` 放在 Skill 安装目录内，首次升级前先备份。使用新版工具的 `migrate --from 原档案路径` 迁移，原文件保留；已移动的备份含相对项目路径时，另用 `--base-dir 原注册表目录` 保持路径含义。目标已有数据时不会覆盖。
3. 运行 `validate`。旧版 `run` 字符串会收到迁移提示。核对真实 CLI 后转成 `argv` 和结构化 `args`，先用 `plan` 检查，详见[迁移指南](skills/wuwu-intelligence/references/registry-guide.md#从旧格式迁移)。

早期将整个仓库克隆进 Skill 目录的安装方式，还需调整为仅包含 `skills/wuwu-intelligence` 的内容，确保 `SKILL.md` 位于已安装目录第一层。

## 设备注册表

在仓库根目录可运行以下命令；使用已安装 Skill 时，把脚本路径换成其实际位置：

```bash
# 创建空档案；重复执行不会覆盖
python skills/wuwu-intelligence/scripts/device_registry.py init

# 校验格式与列出设备，不连接硬件
python skills/wuwu-intelligence/scripts/device_registry.py validate
python skills/wuwu-intelligence/scripts/device_registry.py list
```

默认档案位于用户目录 `~/.wuwu-intelligence/devices.json`，与当前终端和 Skill 安装位置无关。路径优先级为 `--registry` → `WUWU_DEVICES_FILE` → 默认路径。将下面的单台设备对象保存为 `my-led.json`，替换为真实路径和命令；描述文件不需要外层 `devices` 数组：

```json
{
  "name": "my_led",
  "aliases": [
    "灯板"
  ],
  "project_path": "/path/to/your/project",
  "commands": {
    "fade": {
      "desc": "平滑渐变到指定亮度",
      "argv": [
        "{python}",
        "pc/led_cli.py",
        "fade",
        "{n}"
      ],
      "args": {
        "n": {
          "type": "integer",
          "description": "目标亮度",
          "minimum": 0,
          "maximum": 255,
          "default": 128
        }
      },
      "idempotent": true,
      "timeout": 10
    }
  },
  "manual": "docs/manual.html"
}
```

通过命令登记，无需编辑整份设备列表：

```bash
python skills/wuwu-intelligence/scripts/device_registry.py register --file my-led.json --dry-run
python skills/wuwu-intelligence/scripts/device_registry.py register --file my-led.json
python skills/wuwu-intelligence/scripts/device_registry.py show my_led
```

更新时先 `show` 取得当前 `revision`，再使用 `update my_led --file changes.json --if-revision <revision>`；变化文件只写需要修改的字段。Agent 自行传递版本标识，无需用户手动管理。

工具会保留其他设备和未涉及的命令，先校验、备份再原子写入。多个进程可同时登记；过期更新返回 `E_CONFLICT`，需要重新读取并检查差异。完整用法及合并规则见[登记与更新指南](skills/wuwu-intelligence/references/registry-guide.md#登记查看与更新)。

`{python}` 使用运行工具的 Python。`argv` 每项是一个完整参数；`args` 支持类型、数值范围、枚举和默认值。项目的相对路径以注册表所在目录为基准，推荐记录绝对路径。

登记好上面的命令后，可以先检查默认亮度的执行计划：

```bash
python skills/wuwu-intelligence/scripts/device_registry.py plan 灯板 fade
```

`plan` 不启动程序、不探测连接；将 `plan` 换成 `run` 才会调用真实设备 CLI。需要传值时使用 `--args` JSON 参数，详见[参数及执行说明](skills/wuwu-intelligence/references/registry-guide.md#预览与执行)。

完整示例见 [devices.json.example](skills/wuwu-intelligence/devices.json.example)。默认 `devices` 为空；通过接入工作流完成的设备由 Agent 登记，无需手写 JSON。

## 没有硬件也能完整跑一遍

```bash
python tools/check_workflow.py
```

这条命令会创建隔离的 Skill 和设备档案，启动仅监听本机的 TCP 模拟设备，实际验证登记、更新、新命令执行、过期版本冲突、状态回读、错误参数、中文传输、超时不重试、档案迁移和说明书生成。它不读写你的默认设备档案，也不操作真实硬件。

日志、逐步结果和生成的说明书保存在 `.workbuddy/verification/`。模拟设备源码及单独运行方式见 [examples/simulated-led](examples/simulated-led/README.md)。

这验证的是软件调度与 TCP 回路；固件烧录、串口、BLE 和真实设备效果仍需对应硬件验证。

## Demo 与本地预览

[在线 Demo](https://aiflyf.github.io/wuwu-intelligence/) 支持 7 种灯效、示例口语输入、亮度调节、暂停和自动轮播，并展示对应的示例 CLI 与协议消息。它采用有限的本地规则识别输入，未调用真实 Agent。

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory docs
```

打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)。页面使用 ES modules，需要 HTTP 服务，不能直接双击 HTML 来体验完整交互。

- JS、样式、字体和 three.js 均随仓库提供，不依赖 CDN。
- 正文和 2D 灯阵先显示；3D 按需加载，失败时仍可操作 2D 演示。
- 支持移动端、键盘操作及减少动态效果设置；离屏或后台停止场景动画。
- 禁用 JavaScript 时，介绍、安装说明和静态灯阵仍可阅读。

GitHub Pages 可选择 `main` 分支的 `/docs` 目录发布；本地改动需要提交并发布后才会出现在在线页面。

## 开发与验证

运行核心检查需要 Python 3.10+、PyYAML；前端逻辑测试使用 Node.js 20+。展示页无需构建或安装 npm 依赖。

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_skill.py
python -m unittest discover -s tests -v
node --test
```

真实浏览器检查可选安装 Playwright：

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python tools/check_demo.py
```

浏览器脚本自行启动本地临时服务，检查桌面、窄屏、键盘、剪贴板失败提示、无 JavaScript、3D 降级，以及说明书模板的复制和渲染行为。截图保存在被 Git 忽略的 `.workbuddy/qa/`。GitHub Actions 配置了 Windows / Linux 核心检查与 Chromium 页面检查。

这些检查不需要硬件，**不能代替固件编译、真实通信和实物验证**。实际跑通的流程与结果见[软件与模拟通信验收报告](docs/verification.md)，项目问题与后续建议见[维护记录](docs/maintenance-review.md)。

## 目录与参考

```text
skills/wuwu-intelligence/
  SKILL.md                  入口、路由与执行规则
  scripts/device_registry.py 档案登记、并发更新、备份与命令调度
  devices.json.example      结构示例，初始设备为空
  references/               接入、协议、扩展、排障与说明书模板
docs/                       静态 Demo 与维护记录
tools/                      Skill 校验、全流程验收和浏览器检查
examples/simulated-led/      可实际连接的本机 TCP 软件设备
tests/                      核心、前端逻辑和资源完整性回归测试
.github/workflows/ci.yml     持续检查
.claude-plugin/marketplace.json  插件市场清单
```

| 文档 | 用途 |
|---|---|
| [注册表指南](skills/wuwu-intelligence/references/registry-guide.md) | 字段、参数、预览、执行与旧格式迁移 |
| [新设备接入](skills/wuwu-intelligence/references/new-device-playbook.md) | 型号、工具链、接线、开发与交付 |
| [协议模板](skills/wuwu-intelligence/references/protocol-template.md) | 消息分帧、参数和错误处理 |
| [扩展指南](skills/wuwu-intelligence/references/extension-guide.md) | 现有设备增加能力 |
| [排障决策树](skills/wuwu-intelligence/references/troubleshooting.md) | 通信、供电、编译与烧录问题 |
| [创意工坊](skills/wuwu-intelligence/references/idea-workshop.md) | 根据现有材料设计方案 |
| [说明书生成](skills/wuwu-intelligence/references/delivery-doc-guide.md) | 生成可交付的本地 HTML 文档 |

## 隐私与许可

设备档案、IP 和项目路径保存在本地。WiFi 密码等凭据应放在设备项目中被 Git 忽略的本地配置，不写入注册表、说明书或提交记录。更新 Skill 前备份设备档案。

代码与工作流采用 [MIT License](LICENSE)。Demo 的 three.js 与字体授权见[第三方素材说明](docs/assets/vendor/LICENSES.md)。
