# 已有设备扩展新功能(三步法)

用户说"给灯板加个显示文字的功能"这类需求时:

## 第0步:确认需求
- 用大白话复述要做的效果,确认理解一致
- 判断是"纯PC端逻辑"(如组合现有指令的定时脚本,不用动固件)还是"需要新固件指令"(如新动画)
- 能用现有指令组合实现的,优先写Python脚本,免烧录

## 需要新固件指令时的三步法

### 1. 固件(firmware/xxx.ino)
- processLine() 加 `else if (strcmp(cmd, "newcmd") == 0)` 分支
- 是动画:AnimMode 枚举加状态 + updateAnimation() 的 switch 加 case(基于millis节拍)
- 命令函数模式:const char* 返回错误串(nullptr=成功),分发处统一 sendResponse 恰一次
- 协议表同步更新项目 README

### 2. Python库(pc/xxx_dev.py)
- 加同名语义方法:return self._send({"cmd":"newcmd", ...参数})
- docstring 写清参数含义和默认值

### 3. CLI(pc/xxx_cli.py)
- sub.add_parser("newcmd", help="中文说明") + 参数
- main() 分发处加对应调用

## 验证流程
1. python -m py_compile 改过的 .py
2. 固件重新编译烧录(流程D,先跟用户确认)
3. 逐个入口实测:CLI子命令 → 库方法 → 异常路径(错误参数应返回ok:false)

## 纯PC端扩展示例
- 定时任务:while+sleep 组合现有指令(注意捕获异常保证退出时恢复安全状态)
- 组合效果:多条指令编排(demo.py 就是范例:EFFECTS列表驱动)
