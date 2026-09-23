# 交付说明书(HTML)生成指南

新设备接入完成、或已有设备扩展功能后,生成一份 `<project_path>/docs/manual.html`,路径写进 devices.json 的 `manual`。目的:用户不用问 AI 也能自己用、自己排障、自己给别人看。

## 做法:填模板,不从零写

1. 读 `references/manual-template.html`,复制到 `<project_path>/docs/manual.html`
2. 替换所有 `{{占位符}}`;表格行、命令小节、FAQ 条目按实际数量增删(模板里各放了 2-3 个做样子)
3. 按设备类型改 `:root` 里的四个主题变量,模板顶部注释给了四套预设;浅色预设要把 `<body>` 的 `{{HERO_MODE}}` 填成 `light-hero`,深色留空。不像任何一类的就自己配一套,主色要和点缀色有对比
4. 不需要的节整段删掉,别留空壳;接线图没有就删掉整个 wiring 节

## 内容来源(全部来自 devices.json,不读代码)

| 模板节 | 来源 |
|---|---|
| 顶部 hero | `description` / `hardware.*` / `control.transport`;3D 背景自动取主题色,不用管 |
| 接线 | 接入时画的那张 ASCII 图 |
| 怎么开始 | 通电 → 看什么提示(串口日志 / 指示灯)→ 在 Claude Code 里说什么。3 步以内 |
| 你可以这样说 | 每条 `commands[*]` 一行:左列根据 `desc` 写 1-2 个自然说法(如"变红""调暗点"),右列放 `desc` |
| 命令行用法 | 每条 `commands[*]` 一个小节:`run` 进命令块,`args` 写成一句话;末尾表格放 `global_options` |
| 错误码 | 模板已含 protocol-template 的统一错误码表,该设备没实现的删掉 |
| 常见问题 | 从 troubleshooting.md 挑与该设备相关的 3-6 条,改写成"现象 → 原因 → 怎么办" |
| 安全须知 | 按设备实际情况写:独立供电 / 共地 / 电压 / 电机舵机 / 市电,不套模板 |
| 底部 | `project_path`、固件版本或日期 |

## 设计底线(模板已满足,改动时别破坏)

- 单文件、CSS 内联;正文离线可读。唯一外链是 hero 的 three.js(CDN 动态加载),离线或加载失败自动降级为 CSS 渐变,内容不受影响
- 中文正文 16px,行距 1.75,max-width 880px 居中,表格可横滚,手机可读
- `prefers-color-scheme` 深浅色两套变量;`prefers-reduced-motion` 时停止动画
- 命令块可一键复制;JS 失败不影响阅读
- 不加无意义图标和装饰;每个视觉元素都要帮用户找信息

## 生成后

- 用系统默认浏览器打开(Windows `start docs/manual.html`;macOS `open`;Linux `xdg-open`)
- devices.json 对应设备写 `"manual": "docs/manual.html"`
- 以后用户说"打开说明书 / XX 怎么用" → 直接打开这个文件
- 流程 C 加了新功能 → 只更新"你可以这样说"和"命令行用法"两节,不重写整份
