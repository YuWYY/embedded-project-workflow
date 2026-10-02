# v0.5 SoC交接：支持范围与最短试用

本候选围绕板级依据、原生BD设计和硬件向软件的元数据交接。原创案例位于 [examples/vivado/soc-handoff](../examples/vivado/soc-handoff)，规则位于 [Zynq/MPSoC指南](../skills/embedded-project-workflow/references/zynq-mpsoc.md)与[Vitis指南](../skills/embedded-project-workflow/references/vitis-handoff.md)。实际阶段、检查器修订和未覆盖事项见[本轮验证记录](validation-v05.md)。本轮只交付本地候选。

## 支持与证据矩阵

| 能力或阶段 | 本候选状态 | 边界 |
|---|---|---|
| 板卡资料、参考设计和配置分工 | 指南完成；13例定向行为复核通过 | 一个独立执行上下文；按相关依赖补资料，不要求每次整板审计 |
| MPSoC/GPIO原生BD、output products、wrapper与综合 | A基线、B人工变更后续接、C空目录重建均实际完成原生阶段 | Windows/Vivado2025.1原创窄案例；B/C验收器曾失败，原记录和修订后验分开保留；不是任意SoC工程导入器 |
| 当前BD→XSA→SDT语义检查 | A、B、C实际三源通过；两类陈旧交接和旧记录被拒绝 | 核对实例、兼容类型、地址/长度、通道/宽度及来源身份；不代替软件构建 |
| 用户计数RTL的XSim | 18项正例与2项明确业务负例通过 | 仅证明用户逻辑契约，不证明PS已实际AXI读写 |
| 真人Vivado地址编辑与新代理接续 | 用户实际改地址，新上下文代理读取并接续 | 新地址和空附加BD保留；计数RTL未变；生成、检查与未覆盖软件层分别报告 |
| Vitis组件和目标编译器检查 | 分项核查 | 目录、API或HLS组件存在不足以宣布完整环境可用 |
| A53 standalone平台/domain/BSP/应用构建 | NOT_RUN | 当前未发现配套AMD Arm编译器；保留源码和原生重建说明，不用MicroBlaze代替 |
| 布局布线、bitstream、下载、DDR运行、冷启动、板测 | NOT_RUN | 不在本轮实际验证范围 |
| DMA、缓存、中断、多核/Linux运行 | 分析指南；原生功能NOT_RUN | 不因GPIO交接通过扩大支持声明 |
| CubeMX/FreeRTOS、TouchGFX及此前Vivado案例 | 历史工具证据 | 见[v0.4](validation-v04.md)、[v0.3](validation-v03.md)；本轮仅复验受影响行为 |
| ESP-IDF | 资料与源码层 | 没有原生配置、目标构建或运行验证 |

`NOT_RUN`和实际`FAIL`分开保留；原生阶段成功、检查器修订后的后验成功，也不改写原失败记录。当前结论限定为本案例的硬件设计与软件元数据交接。

## 三个窄命令

检查入口：[soc_handoff.py](../skills/embedded-project-workflow/scripts/soc_handoff.py)。使用已有Python和厂商工具，不安装依赖、不修改全局环境。以下占位值替换为本轮绝对路径，报告目录使用新的隔离目录；先运行各子命令的`--help`核对实际参数。

```text
python -B skills/embedded-project-workflow/scripts/soc_handoff.py doctor --tool-root <AMD工具根目录> --report-dir <新报告目录>
python -B skills/embedded-project-workflow/scripts/soc_handoff.py inspect --bd <当前BD> --xsa <当前XSA> --sdt <system-top.dts> --instance axi_gpio_0 --report-dir <新报告目录>
python -B skills/embedded-project-workflow/scripts/soc_handoff.py verify --bd <当前BD> --xsa <当前XSA> --sdt <system-top.dts> --instance axi_gpio_0 --record <对应当前来源的inspect报告目录/result.json> --expected-base 0xA0010000 --expected-range 0x10000 --report-dir <新报告目录>
```

`doctor`分别判断在盘的工具和目标组件，不启动厂商程序；`inspect`读取当前来源形成观察记录；`verify`核对本次预期及来源/交接状态。`--record`可省略；提供时验证与该记录对应的来源身份，不能把修改前记录用于证明修改后的来源仍相同。原生配置和重建使用案例入口，不由检查器自动修复或下载。记录JSON不是第二套配置源。

原生案例的`run.py`提供子进程`--timeout`，默认900秒，仅代表单次进程等待上限。检查器自身不启动子进程，因此不接收无意义的工具超时参数，进程退出码和超时值为null。非法参数退出2，普通失败/超时退出1，受控中断退出130；工具输出和记录保存失败均不能包装为成功。日志与阶段记录的实际实现以随包脚本及对应测试为准。

解析器无法处理工程、SDT覆盖或地址转换时明确返回支持缺口。AI仍可依据实际工具分析，不能删除节点、改产物或关闭检查来强行通过。

## 原创案例和真人步骤

固定案例采用ZCU102硬件Rev1.0、board file `xilinx.com:zcu102:part0:3.4`、`xczu9eg-ffvb1156-2-e`，仅作为离线参考板。PS HPM0_FPD经SmartConnect访问双通道AXI GPIO，自有计数RTL由通道1控制、通道2读回。board file版本与硬件修订分别记录。

基线地址为`0xA0000000`、范围`0x10000`。PL时钟请求100MHz，接入采用PS传播后的实际频率，保持匹配板卡的参考时钟依据。先形成真实基线，再提供实际工程入口和界面对象名称，请用户在Address Editor改为`0xA0010000`，范围不变，保存并关闭。

新代理只获得当前工程、设计约定和续接记录。它需要读取真人保存的BD，更新相关生成、综合、XSA与SDT，并从最终配置进行空目录重建。旧创建脚本只用于准备基线，不得恢复旧地址。真人阶段未完成时保留待验证，独立工作继续。

交接矩阵已使用两轮真实产物执行：A/A/A、B/B/B通过；B/A/A定位BD→XSA陈旧；B/B/A定位XSA→SDT陈旧；当前B三源引用旧A记录也被拒绝。C空目录重建的三源检查同样通过，GPIO语义与B一致，见[实际矩阵](../examples/vivado/soc-handoff/validation-handoff-20261002.json)。地址相同但GPIO宽度或通道配置不同的拒绝由主机负例覆盖；未将其冒充板上故障。旧结果与当前源码哈希不符时只能作为历史证据。

从真人保存的工程重建，使用案例的[当前配置重建入口](../examples/vivado/soc-handoff/CURRENT_REBUILD.md)，而非旧的初始创建脚本。该入口明确拒绝额外编译宏、自有约束等尚未适配的工程形态；脚本范围不足不代表这些原生功能不能使用。

本轮不要求含时间戳的XSA跨次逐字节一致，也不把新一次成功解释为历史`Tcl_Close`或XSim异常根因已修复。公开包只含原创材料与脱敏结论；厂商框架、完整生成树和原始个人日志留本地。保持未安装、未自动启用、未推送及未发布。
