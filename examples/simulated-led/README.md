# 本机 LED 模拟设备

这是用于验证 Skill 工作流的**软件设备**，只监听 `127.0.0.1`，不连接或控制任何真实硬件。服务端保留颜色、亮度、文字和计数器状态，CLI 通过真实 TCP 连接收发单行 JSON。

在仓库根目录，用 Python 3.10+ 运行：

```bash
# 终端一：启动模拟设备，Ctrl+C 停止
python examples/simulated-led/device.py --port 8765
```

```bash
# 终端二：发送命令，再查询实际保存的状态
python examples/simulated-led/cli.py --port 8765 color 255 0 0
python examples/simulated-led/cli.py --port 8765 status
```

所有响应含 `"simulation": true`。服务端收到 `color` 后，后续 `status` 应返回 `"rgb": [255, 0, 0]`。

完整的隔离验证使用：

```bash
python tools/check_workflow.py
```

它会复制一份独立 Skill、创建专用设备档案、选择空闲端口，然后验证初始化、正式登记与更新、新命令执行、过期版本拒绝、命令预览、执行与状态回读、参数拒绝、中文传输、错误码、延迟响应、迁移和说明书生成。结果与生成的说明书保存在 `.workbuddy/verification/`，不会写入你的默认设备档案。

`fail`、`malformed`、`delayed_increment` 专门用于故障注入：分别模拟外设错误、非法响应，以及“动作已完成但响应迟到”。它们不是实体 LED 的通用指令。

此示例证明本地软件调度和 TCP 回路可以工作；不代表 ESP32 固件、串口、BLE 或真实灯板已经验证。
