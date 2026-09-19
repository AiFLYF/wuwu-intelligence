# 已有设备扩展新功能(三步法)

用户说"给灯板加个显示文字的功能"这类需求时走这里。**只读要改的文件,不通读项目。**

## 第 0 步:确认需求(一句话)
- 用大白话复述要做的效果,用户不反对就开始
- 判断是"纯 PC 端逻辑"(组合现有指令,不用动固件)还是"需要新固件指令"(如新动画)
- 能用现有指令组合实现的,优先写 Python 脚本,免烧录

## 需要新固件指令时的三步法

### 1. 固件(firmware/xxx.ino)
- processLine() 加 `else if (strcmp(cmd, "newcmd") == 0)` 分支
- 是动画:AnimMode 枚举加状态 + updateAnimation() 的 switch 加 case(基于 millis 节拍)
- 命令函数模式:const char* 返回错误串(nullptr=成功),分发处统一 sendResponse 恰一次
- 协议表同步更新项目 README

### 2. Python 库(devices.json 的 control.lib)
- 加同名语义方法:return self._send({"cmd":"newcmd", ...参数})
- docstring 写清参数含义和默认值

### 3. CLI(devices.json 的 control.cli)
- sub.add_parser("newcmd", help="中文说明") + 参数
- main() 分发处加对应调用

## 验证流程
1. python -m py_compile 改过的 .py
2. 固件重新编译烧录(流程 D,一句话告知即可)
3. 自己逐个入口实测:CLI 子命令 → 库方法 → 异常路径(错误参数应返回 ok:false)
4. 只让用户看一眼实物效果

## 收尾(必做)
- devices.json 该设备的 `commands` 加新条目:desc(一句话做什么)/ run(命令模板)/ args(参数含义、范围、默认值);新增的公共参数进 `global_options`
- 有 `manual` 的,更新说明书里"能说的话"和"命令行用法"两节

## 纯 PC 端扩展示例
- 定时任务:while+sleep 组合现有指令(捕获异常保证退出时恢复安全状态)
- 组合效果:多条指令编排(demo.py 就是范例:EFFECTS 列表驱动)
