# 支持范围与证据入口

本页对应 **v0.7.0-beta.1 公开预览版**。公开发布状态、附件及发布提交以[本版本 Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.7.0-beta.1)为准；远端检查以[CI 的对应提交记录](https://github.com/YuWYY/embedded-project-workflow/actions/workflows/validate.yml)为准，不把本地通过或历史 CI 当成当前提交通过。

发布阶段新增两次独立执行为 1 PASS / 1 FAIL；审阅反馈后的补验 PASS，未将其改写为首次全通过。见[发布前完善与验证](validation-v07-release.md)。

下面保留发布前本地验收的证据范围；详情见 [v0.7 验证记录](validation-v07.md)、[失败与修订](failures-v07.md)。这些历史记录中的“候选”“未发布”“远端 CI NOT_RUN”描述当时状态，不替代实际发布记录。下载文件不会安装或自动启用 Skill。

## 当前可用能力

| 能力 | 指南/脚本范围 | 本轮实际证据 |
|---|---|---|
| 看懂现有工程 | IOC、TouchGFX、XPR/BD 的有限格式；CMake/preset/toolchain 仅静态声明；不执行配置命令 | 51项 Windows/Linux、普通与-O四组通过；142项整体Python回归普通/-O通过 |
| 旧 Vivado BD 部分读取 | 仅2020.2/PS7 5.5已确认的重复address_block形态；不解释有效地址空间，不改BD | 同一公开子集保留8个实例、13条有序地址块；PARTIAL，不是原生执行资格 |
| 从概览给出下一步 | 识别当前入口、实现位置、相关改动与缺口；[调用说明](../skills/embedded-project-workflow/references/execution-entries.md)在Skill包内 | 首轮单位说明失败后，首次概览与不受窄执行器支持的工程分析定向复测通过 |
| 在裸机已有工程接入功能 | 保留当前主循环、导航和构建结构 | F103/CMake真实Debug、实际业务源码主机验证、ELF/MAP接入；初始两版长运行计时缺陷保留，候选重做通过独立长期契约 |
| 接续应用参数修改 | 用户配置继续作为来源，不强制重生成 | 两版均保留250ms与新菜单名，当前构建及独立主机/调用检查通过；修改为明确的测试输入 |
| CubeMX跨版本再生成 | 独立6.15.0来源副本→本机6.18.1/F1 1.8.6/CMake；明确迁移准备 | 两次实际生成、构建和新构建目录复验；不等于运行过6.15.0或任意工程无损迁移 |
| 检查器能否识别失败 | 原创业务四种逻辑负例、缺输入/错误编译、漏调用及陈旧记录 | 按具体原因拒绝；漏调用的目标仍可编译，接入检查失败 |
| CI | 现有统计与Model检查保留；新增状态模块主机契约定义 | 发布前本地Windows/Linux检查通过；远端状态查[对应提交的CI](https://github.com/YuWYY/embedded-project-workflow/actions/workflows/validate.yml)，此表不预填通过 |
| 新用户真人试用 | [待用步骤](first-use.md#尚待开展的首次真人试用) | NOT_RUN，没有模拟真人反馈 |

原始10次行为执行7 PASS/3 FAIL，后续定向2+1次通过；详细[逐项结果](../evaluations/v07/results.json)保留功能、保护、证据与说明四维，不能合并成13次初次全通过。最终r2未全场景重跑，部分代理仍过度读取，部分完整契约由独立复核补足。

## 保持原有窄执行边界

| 入口 | 能做什么 | 不能从本轮推定什么 |
|---|---|---|
| project_intake | stdout只读观察、稳定字段与局部诊断；无厂商工具亦可运行 | 配置正确、生成或构建成功、任意格式完整支持 |
| cubemx_rtos | 固定G474RE/Cube6.18.1/G4 1.6.3/ST CMSIS2/ARMCC5.06u7形态的已有栈与静态队列容量调整 | F103/CMake已加入该执行器、任意RTOS工程导入或对象创建 |
| touchgfx_project | 固定4.26.1/Simulator布局的既有工程生成与构建 | 自动实现按钮业务、任意硬件界面或真实交互均通过 |
| soc_handoff | 支持形态的BD/XSA/SDT语义与来源检查 | 自动生成这些输入、任意SoC平台/BSP/应用已构建 |

## 历史结果与当前缺口

CubeMX/FreeRTOS、TouchGFX、Vivado、Zynq/MPSoC等指南继续可按目标使用，历史原生案例仅证明当时来源与环境。本轮没有机械重跑未修改的TouchGFX、Vivado/FIFO流程。

Vitis A53平台/domain/BSP/应用原生构建、ESP-IDF原生构建、板级运行与OLED视觉/按键电气验证仍为 **NOT_RUN**。Cortex-M的ARM GCC构建不能代替A53软件环境验证。硬件操作、下载、串口、调试器均未执行。

历史入口：[v0.6](validation-v06.md)、[v0.5](validation-v05.md)、[v0.4](validation-v04.md)、[v0.3](validation-v03.md)、[更早记录](validation.md)。历史文件中的“本轮”属于其原阶段，原始结论不倒改；公开发布状态应另查[实际 Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.7.0-beta.1)。

完整源码包包含原创示例与检查，Skill ZIP只含Skill目录及许可。第三方完整工程、厂商树、私有工程、原始个人日志和固件不进入公开发行物。取得文件不等于安装或授权执行；继续按本轮任务明确显式读取与操作范围。
