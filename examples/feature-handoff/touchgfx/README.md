# TouchGFX 既有工程功能接手

使用本机已有 TouchGFX 4.26.1 / Simulator 2.0.0，480×272 RGB565。
本目录仅含原创配置与用户实现，不含厂商框架、模板、字体及完整生成树。

## 三个阶段

1. **准备基线**：`CounterHandoff.touchgfx`、`texts.xml`、`application.config` 和 `user/` 定义 Dashboard / Controls、计数与暂停。仅在新的空目录使用 `setup.py`；设计约定见 [PROJECT.md](PROJECT.md)。实际生成和干净 Simulator 构建通过后，交给独立代理。
2. **接入统计**：[implementation/](implementation/README.md) 保存首次接手结果。原生配置增加 Statistics 页面及导航，用户 Model 使用共享滚动统计核。实际生成、干净构建通过；准备基线保留。
3. **真人结构变化与接续**：从统计工程建立另一份人工副本，由用户在 Designer 添加 Reset 按钮及 `resetStatistics` 交互。新代理读取当前设计，沿用户 View / Presenter / Model 实现清空；不恢复前两个阶段的配置。当前完成状态见 [v0.4验收记录](../../../docs/validation-v04.md)。

`setup.py` 只准备新基线。继续已有工程用 Skill 随包的 `touchgfx_project.py inspect/generate/build`，不能用准备脚本覆盖真人设计。`build` 包含生成及干净构建。传给 `--touchgfx-root` 的工具根下应直接包含 `designer/tgfx.exe`、`env/MinGW/bin/g++.exe` 和 `touchgfx/`；准备模板还需 `app/packages/`。不要仅按版本号推测子目录，具体布局以入口检查为准。

## 主机业务检查

在仓库根目录运行：

```text
python -B examples/feature-handoff/touchgfx/tests/check_model.py --project <实际统计工程目录> --touchgfx-root <TouchGFX工具根目录> --output <新的独立报告目录>
```

实际 Model 接通 `resetStatistics()` 后增加 `--with-reset`。它执行实际 Model / 统计源码，验证采样节拍、窗口、暂停与部分周期保留；Reset 阶段还将清空调用替换为空操作，要求相同契约检查失败。替换仅用于独立编译对象，不修改工程源码。

测试需要本机已有 MinGW；使用该工具链匹配的进程 PATH，避免其他 C++ DLL 导致程序尚未进入业务代码就退出。测试结果为主机业务证据，不是 GUI 点击、原生页面切换或板测。

## 人工操作与验收

在人工副本的 Statistics 页面添加 Flex Button。**Name** 为 `resetButton`，启用 Text 视觉元素后显示 **Reset**；交互设置 **Button is clicked → resetButton → Call new virtual function → resetStatistics**。位置使用右侧空白处，避免覆盖已有统计与导航。保存、生成、关闭后由接续代理检查当前原生文件。

界面验证单独进行：先暂停，进入 Statistics，点击 Reset，样本数应为 0，统计值显示无数据；计数及暂停状态保留。切页应保留状态；恢复后继续当前进度采样。构建通过不证明空虚函数已接通业务。

本轮真人接续已完成，交付 [最终用户层与配置快照](human-continuation/README.md)。实际用户交互名为默认 `function1`，AI沿用该入口而非要求回到计划名称；用户报告五项Simulator验证均通过，详情按原生生成、主机检查和人工反馈分别记录。
