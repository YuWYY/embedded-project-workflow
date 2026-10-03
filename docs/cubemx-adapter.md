# 既有CubeMX / RTOS工程：最短调用路径

本页说明当前窄执行入口；v0.6 的实际验证状态见[支持与证据](support.md)，末节A/B案例保留历史身份。

这是首批窄适配，不是通用工程导入器。目标范围仍为Windows、CubeMX 6.18.1、G4固件1.6.3、ST CMSIS-RTOS2、ARMCC 5.06 u7 build960、Keil G4 DFP2.0.0与STM32G474RE。所有显式源码、包含目录与链接脚本必须位于隔离工程内部，CubeMX使用库复制方式；链接外部依赖的布局明确拒绝，不能假定来源哈希已经覆盖它们。

只想读当前配置且没有这些工具时，先用[无需厂商工具的只读入口](first-use.md)。本页 `cubemx_rtos.py inspect` 仍需核查固定执行profile；不要把它和 `project_intake.py inspect` 的有限来源观察混为一谈。

已有任务只按名称修改 `stack_words`，保留Static/Dynamic；已有静态 `uint32_t` 队列只改 `capacity_elements`。入口、优先级、顺序、存储符号及其他原生字段保留。栈words和队列元素在本目标中分别换算为4字节；这不是其他平台的单位默认值。

## 检查、计划、执行

以下命令在仓库根运行。替换尖括号占位符。工具参数为已有安装路径，工作工程须是原件之外的独立副本；不复制正式Git远端、个人调试会话和无关产物。

```text
python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py doctor --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py inspect --project <工程目录> --ioc <工程.ioc> --uvprojx <工程.uvprojx> --target <目标名称> --user-source <用户任务实现.c> --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py plan --project <工程目录> --ioc <工程.ioc> --uvprojx <工程.uvprojx> --target <目标名称> --user-source <用户任务实现.c> --task-stack Producer=384 --queue-capacity Samples=16 --output <工程外的新计划.json> --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py apply --plan <计划.json> --work-root <已存在的隔离父目录> --reports <工程外的新报告目录> --timeout 360

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py verify --plan <计划.json> --reports <本次apply报告目录>
```

名称和目标值为A案例示意；应使用inspect得到的当前对象。`--user-source` 可重复提供。不同安装或适配器源码、工程文件、生成配套文件有变化时，旧计划不能继续使用。无需为范围内变化逐文件再次批准，但不能略过当前来源校验。

计划是一次性操作记录，IOC仍是参数来源。apply保存IOC、Keil工程与生成配套文件备份，再原子替换IOC，调用CubeMX生成和Keil Rebuild。生成器会改多个文件，不承诺整个工程原子回滚；失败后检查报告、当前差异和备份，不拿旧MAP或AXF代替新结果。

verify同时核对当前源文件身份、生成参数、唯一对象创建、用户入口实际所属对象、编译引用、静态存储尺寸与本次产物；改了用户代码但未构建时旧结果必须失效。

`apply --timeout` 可省略，默认360秒；它是每个CubeMX/Keil子进程的等待上限，不是整次任务上限或硬件参数。值必须是正有限秒数，0、负数、NaN、无穷和无效文本在读取计划或创建输出目录前拒绝。遇到不支持的形态应分析原因，不编辑计划或取消检查来硬闯。

## 终态与失败后接续

报告分别保留生成、构建、后验检查的状态。厂商进程结束后再检查日志、产物及接入；`exit_code`保留真实进程返回码，`terminal_state`说明该阶段最终结论。进程退出0但缺少当前产物、源码在构建中变化或MAP接入不符，仍会记录后验失败。Keil退出1只有与真实零错误摘要及其余检查一致时才可接受，不能把所有非零码改成成功。

启动失败时实际进程返回码为空；超时和中断记录真实退出码、清理状态与已留下的日志，后续未执行阶段保持NOT_RUN。故障发生在无子进程的验证阶段时，总结的当前返回码为空，已完成构建的返回码仍在对应记录中。

首个状态记录写入失败时不启动工具或修改IOC；末次写盘失败时CLI非零退出，不宣称本次结果已保存。持续存储故障或强制结束仍可能留下RUNNING，它表示需要结合进程、源码和产物重新核对，不能当成成功或自动重新启动的依据。

## 原创A/B基线（历史案例）

基线建立入口为 [setup.py](../examples/cubemx-rtos/adapter-fixture-b/setup.py)，使用 `--fixture a` 或 `--fixture b`，再提供 `--work-root`、`--reports` 与doctor相同的五个工具参数。两个输出目录都须为新的、相互分离的仓库外目录。

- A使用 [原始IOC与APP](../examples/cubemx-rtos/README.md)：Producer静态栈256→384，Samples静态容量8→16。
- B使用 [不同模块路径和对象顺序的原始输入](../examples/cubemx-rtos/adapter-fixture-b/telemetry_fixture.ioc)：Logger动态栈320→448，Sampler静态192保持，Frames静态容量12→20。

先由真实工具建立可构建基线，再作为适配器输入。设置脚本与适配器职责分开：前者创建原创测试输入，后者检查并修改已有工程。历史结果与限制见 [v0.3候选验收](validation-v03.md)，本轮结果见[支持表](support.md)；不包含上板调度、栈水位、堆峰值或通信运行证据。
