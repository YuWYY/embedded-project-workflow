# 既有CubeMX / RTOS工程：最短调用路径

这是首批窄适配，不是通用工程导入器。仅支持Windows、CubeMX 6.18.1、G4固件1.6.3、ST CMSIS-RTOS2、ARMCC 5.06 u7 build960、Keil G4 DFP2.0.0与STM32G474RE。所有显式源码、包含目录与链接脚本必须位于隔离工程内部，CubeMX使用库复制方式；链接外部依赖的布局明确拒绝，不能假定来源哈希已经覆盖它们。

已有任务只按名称修改 `stack_words`，保留Static/Dynamic；已有静态 `uint32_t` 队列只改 `capacity_elements`。入口、优先级、顺序、存储符号及其他原生字段保留。栈words和队列元素在本目标中分别换算为4字节；这不是其他平台的单位默认值。

## 检查、计划、执行

以下命令在仓库根运行。替换尖括号占位符。工具参数为已有安装路径，工作工程须是原件之外的独立副本；不复制正式Git远端、个人调试会话和无关产物。

```text
python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py doctor --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py inspect --project <工程目录> --ioc <工程.ioc> --uvprojx <工程.uvprojx> --target <目标名称> --user-source <用户任务实现.c> --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py plan --project <工程目录> --ioc <工程.ioc> --uvprojx <工程.uvprojx> --target <目标名称> --user-source <用户任务实现.c> --task-stack Producer=384 --queue-capacity Samples=16 --output <工程外的新计划.json> --cubemx <STM32CubeMX.exe> --firmware <G4固件目录> --uv4 <UV4.exe> --armcc <armcc.exe> --pack <DFP2.0.0目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py apply --plan <计划.json> --work-root <已存在的隔离父目录> --reports <工程外的新报告目录>

python -B skills/embedded-project-workflow/scripts/cubemx_rtos.py verify --plan <计划.json> --reports <本次apply报告目录>
```

名称和目标值为A案例示意；应使用inspect得到的当前对象。`--user-source` 可重复提供。不同安装或适配器源码、工程文件、生成配套文件有变化时，旧计划不能继续使用。无需为范围内变化逐文件再次批准，但不能略过当前来源校验。

计划是一次性操作记录，IOC仍是参数来源。apply保存IOC、Keil工程与生成配套文件备份，再原子替换IOC，调用CubeMX生成和Keil Rebuild。生成器会改多个文件，不承诺整个工程原子回滚；失败后检查报告、当前差异和备份，不拿旧MAP或AXF代替新结果。

verify同时核对当前源文件身份、生成参数、唯一对象创建、用户入口实际所属对象、编译引用、静态存储尺寸与本次产物；改了用户代码但未构建时旧结果必须失效。每个厂商子进程采用360秒等待上限，遇到不支持的形态应分析原因，不通过编辑计划或关闭检查硬闯。

## 原创A/B基线

基线建立入口为 [setup.py](../examples/cubemx-rtos/adapter-fixture-b/setup.py)，使用 `--fixture a` 或 `--fixture b`，再提供 `--work-root`、`--reports` 与doctor相同的五个工具参数。两个输出目录都须为新的、相互分离的仓库外目录。

- A使用 [原始IOC与APP](../examples/cubemx-rtos/README.md)：Producer静态栈256→384，Samples静态容量8→16。
- B使用 [不同模块路径和对象顺序的原始输入](../examples/cubemx-rtos/adapter-fixture-b/telemetry_fixture.ioc)：Logger动态栈320→448，Sampler静态192保持，Frames静态容量12→20。

先由真实工具建立可构建基线，再作为适配器输入。设置脚本与适配器职责分开：前者创建原创测试输入，后者检查并修改已有工程。当前结果与限制见 [候选验收](validation-v03.md)；不包含上板调度、栈水位、堆峰值或通信运行证据。
