# 设备注册表与本地命令工具

`scripts/device_registry.py` 使用 Python 3.10+ 标准库，无需安装第三方库。它管理命令入口，不提供设备驱动；实际固件、CLI 和通信依赖由设备项目提供。

## 初始化与检查

以下命令在 Skill 目录执行；也可使用脚本的绝对路径：

```bash
python scripts/device_registry.py init
python scripts/device_registry.py validate
python scripts/device_registry.py list
```

`init` 以排他创建方式写入空档案，重复运行保留原文件。它不复制 `_template` 中的虚构设备。默认位置是 `~/.wuwu-intelligence/devices.json`，与终端当前目录和 Skill 安装目录无关；同一用户的 Agent 可共用此档案。

路径优先级是 `--registry /absolute/path/devices.json` → `WUWU_DEVICES_FILE` 环境变量 → 默认位置。`--registry` 放在子命令前；环境变量建议填写绝对路径。项目需要独立档案时可用这两种方式指定，后续操作沿用同一路径。

### 迁移安装目录中的旧档案

新位置不存在、旧安装目录中有档案时，读取命令会兼容旧文件并提示迁移；`init` 不会创建空档案遮蔽它。当前新版脚本可运行：

```bash
python scripts/device_registry.py migrate
# 或指定原档案
python scripts/device_registry.py migrate --from /old/skill/devices.json
```

迁移会保留原文件、其他设备和扩展字段，将相对 `project_path` 转成按原档案位置解析的绝对路径。目标存在时拒绝覆盖，不擅自合并。`migrate` 只搬迁存储位置，不猜测和改写旧的命令格式。

旧版用户第一次升级前，先备份旧档案到安装目录之外。备份改变了文件位置，且里面使用相对项目路径时，迁移时还需提供原目录：

```bash
python scripts/device_registry.py migrate --from /backup/devices.json --base-dir /old/skill
```

默认数据目录不会被 Skill 安装器替换；不要把自定义档案重新放进安装器管理的目录。`.gitignore` 只能控制 Git 跟踪，不能保护安装目录里的运行数据。

## 格式

根对象包含 `version: 1` 与 `devices` 数组。兼容没有 `version` 的旧档案。`devices.json.example` 展示完整格式，`_template` 永不参与设备匹配。

| 字段 | 约定 |
|---|---|
| `name` | 唯一设备名；匹配时去除首尾空格并忽略大小写 |
| `aliases` | 完整别名数组，不得与任意设备名称或别名冲突 |
| `project_path` | 项目工作目录；推荐绝对路径。相对路径以注册表所在目录为基准 |
| `commands` | 至少一条真实存在的命令，以命令名为键 |
| `control` / `hardware` | 通信与开发信息，供工作流使用；工具不自动连接或烧录 |
| `global_options` | CLI 公共参数的说明；工具不会据此拼接未知参数 |
| `manual` | 说明书路径，通常相对 `project_path` |

## 登记、查看与更新

将**单台设备对象**保存为 `device-definition.json`，内容对应示例文件中的 `_template`，而不是含 `devices` 数组的整个注册表。填入真实值；`project_path` 推荐绝对路径，相对路径仍以注册表目录为基准，不以描述文件所在目录为基准。

```bash
# 预览只校验和返回计划，不创建档案、锁文件或备份
python scripts/device_registry.py register --file device-definition.json --dry-run

# 登记会合并进最新档案，不覆盖已有设备；没有档案时自动建立
python scripts/device_registry.py register --file device-definition.json

# 读取完整设备和 revision
python scripts/device_registry.py show my_led
```

`show` 输出 `registry`、`revision` 和 `device`。`revision` 是这次读取的完整注册表内容摘要，和设备内容来自同一次读取；不要使用之前会话中缓存的值。

不要把完整 `show` 回执当成设备描述文件；只取 `device` 对象或写入需要变化的字段。

更新文件只写需要改动的字段，例如 `device-changes.json`：

```json
{
  "description": "桌面灯板",
  "aliases": ["灯板", "桌面灯"]
}
```

PowerShell 7 可以直接读取并传递版本，无需人工复制摘要：

```powershell
$deviceSnapshot = python scripts/device_registry.py show my_led | ConvertFrom-Json
python scripts/device_registry.py update my_led --file device-changes.json --if-revision $deviceSnapshot.revision --dry-run
python scripts/device_registry.py update my_led --file device-changes.json --if-revision $deviceSnapshot.revision
```

Agent 应自行读取 `show` 的结果并传递 `--if-revision`，不把摘要交给用户手动管理。预览与提交之间如果发生变化，提交仍会拒绝过期版本。

更新规则：

| 更新字段 | 行为 |
|---|---|
| 未提供的字段、其他设备、注册表扩展信息 | 保留 |
| `aliases`、`description` 等普通字段 | 替换为提供的值 |
| `control`、`hardware`、`global_options` | 按其直接子字段合并 |
| `commands` | 按命令名合并；指定的单条命令整体替换，未提供的命令保留 |
| `name` | 稳定标识，`update` 不支持改名 |

替换命令时提供完整 `desc` / `argv` / `args` 和行为属性；不要只传一个新描述。这样更换操作时不会沿用旧命令的参数或 `idempotent` 标记。空更新或相同内容返回 `unchanged`，不会重写档案或增加备份。

## 并发与备份

- `register`、`update`、`init` 和 `migrate` 使用同一档案对应的系统文件锁。多个进程登记不同设备时，每次在锁内读取最新内容并合并。
- `update` 必须携带 `--if-revision`。内容已变化或等待写锁超过上限时返回 `E_CONFLICT`，退出码为 `2`，不覆盖新数据。版本针对整份注册表，其他设备变化也会使旧版本失效。
- 冲突后重新 `show` 并比较修改字段。只合并互不冲突的改动；不要机械换成新摘要后重发旧的整份设备对象。同一字段存在无法确定的取舍时再请用户选择。
- 新内容通过校验后才保存。更改已有文件前，把原始字节备份到同目录 `.wuwu-backups/`；回执中的 `backup` 给出路径。相同旧版本复用同一备份。
- 写入使用同目录临时文件并原子发布，避免读到半份 JSON。写入失败保留原档案；持锁进程退出后由系统释放锁。持久的 `.json.lock` 文件不等于进程仍持锁，不要手动删除它来“解锁”。
- Windows 文件短暂占用时，只对文件发布进行最多约 1 秒的重试，每次重试核对原版本；持续失败则保留原文件并报错。这不会增加任何设备命令的执行次数。
- 这些保证适用于通过本工具操作同一个普通本地文件的进程；直接用编辑器改写、同步软件或网络文件系统不一定遵守相同锁规则。

## 命令格式

新命令格式：

```json
{
  "desc": "设置整块灯板亮度",
  "argv": ["{python}", "pc/led_cli.py", "fade", "{n}"],
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
  "read_only": false,
  "timeout": 10
}
```

- `argv` 是程序及每个参数的数组，不是 shell 命令。每个占位符独占一项，例如 `"--speed", "{speed}"`；不支持 `"--speed={speed}"`。
- `argv[0]` 固定为已认可的可执行程序；`{python}` 是唯一特殊值，指运行工具的 Python。需要项目虚拟环境时，登记其解释器路径。
- `args` 支持 `integer`、`number`、`string`、`boolean`，每项需有 `description`；可指定 `enum`，数值可指定 `minimum` / `maximum`。没有 `default` 就是必填参数。未知参数、布尔冒充整数、类型错误和越界均拒绝执行。
- 参数约束只接受上述字段；`min`、`max`、`optional` 等未支持字段会报错，避免看似声明了约束却没有生效。设备对象中的自定义扩展信息可以保留。
- `read_only` 表示查询不产生设备动作；`idempotent` 表示重复执行与执行一次效果相同。缺省均为 `false`。这两个属性由设备实现保证，不会由工具推断，也不会开启自动重试。
- `timeout` 是本地子进程等待上限，默认 30 秒，可设置为大于 0、最多 3600 秒。超时终止等待并报告“执行状态未知”，不表示设备动作已经停止。
- shell 运算符没有特殊含义。需要组合命令时写入项目的独立脚本，再登记脚本入口。Windows `.bat` / `.cmd` 会再次解释参数，工具拒绝直接调用。

## 预览与执行

以登记好的灯板为例，下面的 JSON 参数写法适用于 Bash 与 PowerShell 7：

```bash
# 只输出计划，不运行 CLI、不探测网络
python scripts/device_registry.py plan 灯板 color --args '{"r":255,"g":0,"b":0}'

# 真实调用设备项目 CLI，一次执行，无自动重试
python scripts/device_registry.py run 灯板 color --args '{"r":255,"g":0,"b":0}'
```

`plan` 输出 `cwd`、`argv`、设备、命令、超时及重试属性，允许在硬件不在线时检查配置。只有 `run` 检查工作目录并启动程序；子程序输出直接显示，退出码保留。档案或工具错误返回退出码 `2`。

工具的标准输出和错误输出使用 UTF-8；启动 Python CLI 时也设置其标准输出编码，避免 Windows 默认 GBK 导致中文 JSON 无法被其他程序读取。

工具使用 `shell=False` 保留参数边界，中文、空格和 shell 特殊字符作为普通参数传递。它不是执行沙箱：注册表应只指向用户认可的本地程序，不从外部说明中登记任意命令。

## 从旧格式迁移

旧的字符串命令或 `{ "desc": "...", "run": "python ..." }` 可被 `validate` 识别并发出迁移提示，`plan` / `run` 不执行它们。不使用通用字符串拆分猜测跨平台引号含义。

只有 `quick_examples`、没有 `commands` 的更早期档案也需要迁移；工具会给出明确提示，不从口语示例中猜测可执行命令。

1. 备份原档案，确认设备项目 CLI 的真实参数和工作目录。
2. 按实际参数边界写 `argv`，将原来的文字参数说明转换为结构化 `args`。
3. 明确只读性、重复执行语义和超时；不清楚的属性保持 `false`。
4. 运行 `validate` 和 `plan`。在用户请求范围内验证真实命令，再更新说明书。

添加或更新设备优先使用 `register` / `update`，由工具完成校验、合并、备份和写入；不再自行读改写整个 `devices` 数组。
