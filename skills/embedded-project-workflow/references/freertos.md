# FreeRTOS：可配置的对象骨架与用户实现

涉及任务划分、对象创建、内存策略或RTOS再生成时读取。已有小修改不需要重新规划任务；简单裸机工程不因使用本Skill而引入RTOS。

## 先识别当前实现

读取`.ioc`、生成的RTOS初始化、应用入口、FreeRTOSConfig、实际内核和CMSIS适配器、链接与构建输入。配置描述文件名和GUI菜单版本不等于实际内核版本。核对现有成功结构和[用户设计约定](configuration-contracts.md)。

CubeMX支持的任务、队列、定时器、信号量、互斥量等，可用于用户预设工程骨架。对象类型、分配选项和入口生成方式取决于当前工具、设备包及CMSIS版本；模板里有某个USER CODE区，不证明GUI一定能配置对应对象。

需要规划时使用短表：

**对象/用途｜触发或周期｜优先级依据｜栈/容量及单位｜分配策略｜创建/销毁时机｜配置来源｜应用入口**。

AI根据需求推导建议；用户已有任务职责、数量、接口或内存约定时先沿用。不要把“一项功能一个任务”当默认；按时序和数据关系比较已有任务、ISR、通知、队列、软件定时器及简单循环。

## 创建框架与业务实现

生成器维护其负责的对象声明、属性、创建与入口骨架，独立应用文件维护循环、状态机、协议和算法。对象只保留一个创建来源；不能在APP里另建同名或隐藏线程绕开用户任务配置。

按实际生成器选择支持的用户区、external入口或weak覆盖。已有weak+strong方式可保留，检查MAP中的实际实现；external方式可让遗漏实现变成链接错误。不要强制迁移所有工程，也不要用弱空循环的编译成功证明任务业务已接入。

核对同步对象在首次使用前创建、句柄失败处理以及内核启动关系。工具不能表达的对象通过正式用户扩展创建，说明最终来源，不虚称它已在GUI中配置。对象参数调整遵循用户已授权范围及生成所有权。

## 四种容易混淆的含义

| 概念 | 实际判断依据 |
|---|---|
| RTOS静态/动态内存分配 | 应用是否提供实际对象/栈/队列存储，还是由分配器取得 |
| C的`static` | 变量存储期或文件作用域链接属性，不能独自证明RTOS对象不用堆 |
| 创建时机 | 启动时或运行时创建/删除；启动创建也可能动态分配 |
| 设计期/运行期参数 | 是否需重新生成构建，或当前接口支持运行中修改；静态分配不等于所有属性不可变化 |

固定、长期存在且需要明确内存预算的对象可优先评估静态分配；按需对象或依赖库需要动态时，比较动态或混合策略与失败处理。已有成功工程不自动静态化，也不默认禁用整个堆。[FreeRTOS内存说明](https://www.freertos.org/Documentation/02-Kernel/02-Kernel-features/09-Memory-management/03-Static-vs-Dynamic-memory-allocation)

不要根据`osThreadNew`名称、C `static`声明或界面Static选项直接判断有效分配方式。检查实际属性、适配器、内核及依赖。仅有`.name`的静态CMSIS属性结构，仍可能令对象从堆创建。

例如STM32CubeG4 FW 1.6.3所带FreeRTOS 10.3.1的CMSIS-RTOS2适配器，`osTimerNew`会先为回调包装调用`pvPortMalloc`，随后才选择静态或动态定时器控制块。因此局部Static不等于整个工程无堆。其他版本可能有不同机制；不能把新版本文档直接套给旧源码。[Arm版本相关限制](https://arm-software.github.io/CMSIS-FreeRTOS/v11.2.0/page_technical_data.html)

用户要求“禁止启动后分配”或“全工程不用堆”时，应分别核查任务、同步对象、内核服务任务、封装和库的分配路径；遇到冲突给出匹配版本的方案，不静默改中间件或关闭宏掩盖依赖。

## 参数和实时关系

- 栈深单位先核实。CubeMX某些配置按words，CMSIS-RTOS2 `stack_size`按字节，FreeRTOS原生接口按栈元素计数；检查生成数组、`sizeof`和适配转换，不能直接照抄数字。[CMSIS线程属性](https://arm-software.github.io/CMSIS_6/main/RTOS2/group__CMSIS__RTOS__ThreadMgmt.html)
- 任务优先级与NVIC优先级是不同体系；核对当前CMSIS映射、FreeRTOS配置以及使用RTOS API的ISR约束，不照搬数值。[Cortex-M约束](https://freertos.org/Documentation/02-Kernel/03-Supported-devices/04-Demos/ARM-Cortex/RTOS-Cortex-M3-M4)
- 按真实执行和阻塞关系分析期限、数据所有权及共享资源。高频采样/控制可能属于硬件或ISR，不能为图形上整齐而全部移入任务。
- 栈和队列容量应有用途依据与可调范围。静态链接容量不证明运行栈峰值、无死锁或时限满足；修改优先级也不能替代定位过长临界区或不当阻塞。

## 再生成与验证

由源配置生成后核对对象数、名称、入口、分配属性、容量单位和创建顺序，检查用户实现保留与真实构建引用。只比较本次相关差异，勿把对象表变成每轮必填审计。

分别报告生成、编译链接、结构与主机逻辑、实际调度/栈余量等证据。缺少板测或可信内核执行时，不宣称任务调度、运行期内存和实时性已经通过。相关机制以[CubeMX说明](https://www.st.com/resource/en/user_manual/um1718-stm32cubemx-for-stm32-configuration-and-initialization-c-code-generation-stmicroelectronics.pdf)及本机输出为准。
