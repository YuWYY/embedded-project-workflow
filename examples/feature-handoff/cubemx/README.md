# CubeMX / FreeRTOS 功能接手

先由准备代理建立可生成、构建的原创空闲任务工程，再由独立代理在预设任务和队列中接入滚动统计。设计约定、工具组合和基线准备方法见 [PROJECT.md](PROJECT.md)；完成后的业务源码及重建方法见 [implementation/README.md](implementation/README.md)。

基线源为本目录的 IOC、Services、Domain 和 prepare.py。它只含有效空闲入口，不能作为已实现统计功能的证据。功能结果位于 implementation；不回写或替换基线。原生工程生成到仓库外的全新隔离目录，依赖本机已有 CubeMX、固件包、Keil、ARMCC 和器件包，不自动下载。

保留 SampleFeed 静态任务、StatsWorker 动态任务、SampleQueue 静态队列和 Normal 优先级。业务生产者每10个RTOS tick尝试发送循环样本10～90，消费者沿已有队列更新最近8个成功接收样本；失败发送另计，不增加任务或共享原始样本旁路。

```text
python -B examples/feature-handoff/cubemx/prepare.py --help
python -B examples/feature-handoff/cubemx/implementation/apply.py --help
```

prepare.py 用于新建基线，apply.py 用于本原创案例的功能复建和受限续接；都不是任意用户工程导入器。通用 cubemx_rtos.py 的窄参数修改接口未因此扩充。实际用户工程应读取其当前配置及用户实现，再决定适配方式。

本轮完成真实再生成和Keil Rebuild，并核对入口定义、静态存储、编译引用与MAP。共享纯C模块及任务主机测试另行记录；模拟CMSIS调用不证明真实调度、队列吞吐、栈水位或板上行为。当前验收和问题记录见 [v0.4验证说明](../../../docs/validation-v04.md)。
