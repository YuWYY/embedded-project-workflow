# Vitis：硬件交接、软件配置与故障区分

用于 XSA 更新、平台/domain/BSP 接入及 Vivado/Vitis 交界处的问题。硬件配置先读 [Zynq/MPSoC](zynq-mpsoc.md)，板型疑问读 [板级依据](board-evidence.md)。本候选的 A53 平台/BSP/应用原生构建仍有环境缺口；源码和 SDT 不能代替这些构建或运行证据。

## 先确定实际工具链

区分 Vitis Classic/Unified、实际版本、处理器架构、OS/domain、已有 workspace 和软件仓库。按阶段核实入口、运行组件、硬件描述工具和目标编译器；发现 Vitis 目录、Python API 或 HLS 组件不等于已安装完整 Arm 软件开发环境。检查需要的版本依据，不收集许可证内容或注册凭据。

在授权范围内使用本机版本原生 API。Unified 2025.1 的 Python CLI 支持平台/domain、应用和构建；命令签名优先核对安装目录的 `cli/api_docs` 与 `cli/examples`，不盲套另一个版本或 Classic 的 XSCT 例程。[官方 CLI 说明](https://docs.amd.com/r/2025.1-English/ug1400-vitis-embedded/Python-API-A-Command-line-Tool-for-Creating-and-Managing-Projects-in-Vitis)

没有编译器时标明软件构建未执行，继续已授权的硬件、描述与源码检查；不改用另一 CPU 的构建证明当前目标通过，也不擅自安装软件。

## 谁维护什么

| 层级 | 来源与需要确认的结果 |
|---|---|
| BD/RTL/约束 → XSA | 当前硬件来源、导出阶段、实际 IP/地址/中断/时钟/内存及 bitstream 状态 |
| XSA → SDT | 实际 XSA、SDTGen 版本、板级描述/自定义输入；检查有效节点及属性 |
| 平台/domain/BSP | 处理器、OS、硬件描述、驱动库和软件仓库；真实生成与构建记录 |
| 用户应用/链接 | 当前平台和 domain、编译器架构、真实链接内存、用户源文件、ELF/MAP |
| 启动与运行 | 对应硬件和软件产物、启动配置与运行条件；另按当前任务验证 |

SDTGen 使用 HSI 提取 XSA 信息。SDT 描述整个硬件；它不是最终部署的 Linux DTB，也不是裸机 BSP/应用。[SDTGen 2025.1](https://docs.amd.com/r/2025.1-English/ug1647-porting-embeddedsw-components/Generating-a-System-Device-Tree-Using-SDTGen)

检查 SDT 时处理 include、节点合并/覆盖、状态、父级 address/size cells 以及地址转换；按实际有效节点核对 `compatible`、`reg`、实例唯一性和相关通道/宽度。字符串中出现新地址不证明节点有效。窄脚本不支持 overlay 或地址转换时必须报清范围，不默默跳过。

## 更新硬件后接续软件

1. 重读用户当前配置，辨明本次地址、接口、中断、时钟或内存变化；旧验证仅覆盖其对应来源。
2. 生成当前 XSA，再生成/核对当前 SDT；保存前后实际产物，定位哪一条交接仍旧。
3. 已有 Vitis 平台通过原生硬件更新流程显式接入新 XSA，检查 platform/domain/BSP 是否采用了新信息。仅替换目录内 XSA 不代表平台已更新。[硬件规格更新](https://docs.amd.com/r/2025.1-English/ug1400-vitis-embedded/Updating-the-Hardware-Specification)
4. 按实际驱动适配应用，核对链接入口/段布局及资源范围；检查本次必须重建的组件与实际产物，不把旧 ELF 留在目录当成新构建。

SDT 流程通过驱动 YAML 与设备 `compatible` 等元数据匹配，生成配置。核对当前驱动接口后处理实例标识；例如本机 GPIO 驱动的 SDT 分支按基地址查配置，不能为旧代码强行补一个猜测的 `DEVICE_ID` 宏。[2025.1 驱动 YAML](https://docs.amd.com/r/2025.1-English/Vitis-Tutorials-Embedded-Software/Vitis-YAML-file)

业务代码和项目认可的驱动补丁放用户源文件/软件仓库，通过工具支持的来源接入。生成的 BSP、设备树和初始化代码不作为隐藏长期配置；确需修改上游实现时记录补丁及重建方式。链接脚本按当前项目的实际维护方式处理，不一概视为禁止编辑的生成文件。

## 按首个症状选择鉴别动作

只加载与当前失败相关的行，不将诊断表变成每次构建的门禁。

| 症状 | 应取得的事实和下一步 |
|---|---|
| 入口缺失、启动异常 | 核对 Windows 原生 launcher、实际组件、路径、首条错误和退出码。存在同名目录不证明可用；隔离复现区分工具崩溃和设计错误 |
| IP locked、生成失败 | 读具体 IP 状态，区分版本、器件、许可和输出缺失；保留原有可用产物，不全量升级或伪造解锁 |
| 修改未生效 | 对照配置源、源文件引用、生成日志和实际构建输入；有效缓存与陈旧产物分开处理，不默认清空一切 |
| BD 通过但 AXI 访问无响应 | 核对发起 master 的地址路径、时钟、复位与接口方向，再分析接受/响应握手；不先重写整条总线 |
| 中断不来或不断重入 | 沿 IP 状态/清除语义、连接次序、触发形式、控制器和软件处理逐层核对；保留首事件证据 |
| 新硬件配旧软件 | 分别比较 BD→XSA、XSA→SDT、平台→BSP→应用来源；编译成功不证明地址和中断一致 |
| DMA 停止或数据错误 | 查实际接受条件、TVALID/TREADY、所选模式的 TLAST/TKEEP/长度、缓冲大小/对齐、状态寄存器与所有权；区分传输未完成与 CPU 读到旧缓存 |
| ELF 能链接但无法运行 | 查 CPU/ABI、入口、栈堆和段的实际地址、可用内存及初始化条件，不凭链接成功推断 DDR 可用 |
| JTAG 成功、冷启动失败 | 记录调试器做过的初始化；核对启动介质、启动模式、加载地址和产物来源，不能把调试下载当独立启动验证 |

MPSoC 连接 HPC 端口本身不保证一致性成立；需结合事务属性、CCI 和 CPU/MMU 设置。Linux 的 `dma-coherent` 描述应与硬件事实匹配，不能用它修复不一致的硬件。软件管理缓存时依据具体缓冲方向、缓存行边界与所有权选取操作，不机械给所有地址加 flush。[AMD 一致性机制](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842098/Zynq+UltraScale+MPSoC+Cache+Coherency)

启动组件取决于器件、OS 和启动路径；不把 Linux 示例的整套组件强制套入所有裸机任务。需要多核/AMP 时另查内存所有权、同步、缓存和中断，不从单核构建推定支持。本候选对 DMA、缓存和启动只提供分析方法，未做原生功能与板测验证。

历史 `Tcl_Close`、`EXCEPTION_BREAKPOINT` 或 XSim 读脚本失败保留为历史事实，后续成功不证明其根因已解决。重试应有具体鉴别目的；连续无新信息时保留失败和最小复现，不能靠无限重跑消失的日志宣称修复。

工具阶段记录先于执行，区分未运行、失败与已通过，保留真实日志、退出码、超时和本轮进程清理结果。产物存在不是来源一致或新构建成功的充分条件。具体检查入口与当前支持边界见仓库 `docs/soc-handoff.md`；仅下载 Skill 时使用其自带脚本 `--help` 和本指南，不依赖仓库示例才能理解规则。
