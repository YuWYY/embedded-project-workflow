# 资料来源与采用边界

本 Skill 独立编写，以用户要求及超级电容两轮设计复盘为主要输入。下列公开资料用于核查生成机制或参考组织方式；未整包导入第三方 Skill，未复制其脚本、模板或长篇正文。参考资料中的指令不构成本 Skill 的新增规则。

核查日期：**2026-09-27**。TouchGFX 官方页面当时为 **4.26**；前版STM32来源保留当时读取的分支链接，新增FPGA来源在下文固定提交。AMD的动态文档链接可能指向2026.1；本次实际工具验证使用本机Vivado 2025.1及其模型，不据此升级现用工程。执行项目任务时仍须核对本地版本、工程形态和文件归属。

## 官方机制

| 来源 | 本次采用 | 不据此推断 |
|---|---|---|
| [ST：STM32CubeMX](https://www.st.com/content/st_com/en/stm32cubemx.html) | 配置时钟、引脚与外设后由工具生成初始化代码；经典 CubeMX 的 USER CODE 保留机制 | 保留选项不能代替生成差异和调用链检查；不强制将所有动态工作参数移回图形配置。官网亦说明 CubeMX2 分文件策略，不将经典结构套用到所有版本 |
| [ST：TouchGFX Code Structure](https://support.touchgfx.com/docs/development/ui-development/software-architecture/code-structure) | `generated/gui_generated` 与 `gui` 的职责、基类与用户派生类的扩展方式 | 不因示例路径或名称推断当前工程完全同构；不要求所有自定义行为都由 Designer 表达 |
| [ST：TouchGFX Generating Code](https://support.touchgfx.com/docs/development/touchgfx-hal-development/generator-how-to/generating-code) | CubeMX 与 Designer 的生成衔接、`target/generated` 与可编辑 target 类的边界 | 不认定整个 `target` 都可手改；不为已有用户层小修改强制重复生成 |
| [ST：Modifying Generated Behavior](https://support.touchgfx.com/docs/development/touchgfx-hal-development/generator-how-to/modifying-generated-behavior) | HAL 的用户派生类以及按所选功能生成的扩展接口 | 不把某配置下可编辑的同名文件套用到另一种配置 |
| [ST：Unicode API](https://support.touchgfx.com/docs/api/classes/classtouchgfx_1_1_unicode) | 格式串与 `%s` 参数的不同字符类型、缓冲容量单位及格式支持；用于修复案例04暴露的库契约缺口 | 不以主机标准字符串替身证明 TouchGFX 真正运行，不将格式算术检查等同于界面验证 |

## 相似开源设计

| 来源与核查状态 | 采用点 | 未采用内容 |
|---|---|---|
| [ByTaymur / stm32-firmware-workflow](https://github.com/ByTaymur/embedded-software-skills/blob/main/skills/stm32-firmware-workflow/SKILL.md)；[LICENSE](https://github.com/ByTaymur/embedded-software-skills/blob/main/LICENSE) 为 MIT，署名 Muhammed Taymur，2026 | 通用协作方法与项目事实分层、参数集中维护、按需参考文档 | 不继承强制土耳其语、每次解释写文件、每个未点名文件都追加审批、完整入门访谈和固定工具链要求 |
| [zww666-creater / NUEDC-STM32-MSPM0-SKILL](https://github.com/zww666-creater/NUEDC-STM32-MSPM0-SKILL/blob/main/SKILL.md)；本次根目录无许可证文件，GitHub API 的 license 为 null | 厂商配置源 → 生成工程 → 用户代码层，以及生成后检查差异的思路 | 不复制其文本或脚本；不移植其竞赛范围、平台组合、构建工具或探针步骤。本 Skill 另外明确基础配置与动态参数分工 |
| [MaJerle / stm32-cube-cmake-vscode 转换脚本](https://github.com/MaJerle/stm32-cube-cmake-vscode/blob/main/stm32-cube-cmake-vscode.py) | 分开管理可再生成的构建内容与用户维护内容的方式 | 不引入、运行或改编其转换脚本；不要求用户迁移 CMake/VS Code，不继承强制重生成选项 |

“未发现许可证”只描述本次查询结果，不等同于获准复制或对整个项目作法律结论。本交付仅作来源归因和思想参考；日后若确需复用第三方文件或实质性片段，应先核对相应版本的许可并保留所需署名与许可文本。

没有把上述项目认定为已经覆盖用户要求的 TouchGFX 专用 Skill；TouchGFX 指南按 ST 机制及本任务的配置分工独立制定。来源链接用于追溯，不要求每次普通代码修改重新浏览全部资料。

## Vivado 官方机制

| 来源 | 采用内容与边界 |
|---|---|
| [AMD UG895：XPM](https://docs.amd.com/r/en-US/ug895-vivado-system-level-design-entry/Using-Xilinx-Parameterized-Macros) | HDL中的厂商参数化模块；实例化XPM不等于自行实现底层，也不要求全部封装为Catalog IP |
| [AMD UG896 2025.1：Output Products](https://docs.amd.com/r/2025.1-English/ug896-vivado-ip/Generating-Output-Products)、[脚本示例](https://docs.amd.com/r/2025.1-English/ug896-vivado-ip/Scripting-Examples) | IP配置、生成、OOC/全局综合与仿真分别处理；不把create_ip或DCP存在当成完整功能验证 |
| [AMD UG994：顶层与wrapper](https://docs.amd.com/r/en-US/ug994-vivado-ip-subsystems/Integrating-the-Block-Design-into-a-Top-Level-Design) | 区分工具管理与用户维护的wrapper；端口改变后核对接入，不强制所有工程采用BD |
| [AMD UG892：升级IP](https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Upgrading-IP) | locked状态、旧版static IP产物与正式升级分开判断，不默认升级全部IP |
| [AMD UG835：write_ip_tcl](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_ip_tcl)、[write_bd_tcl](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_bd_tcl)、[report_cdc](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_cdc) | 独立IP/BD导出方式与CDC检查；导出不等于重建，报告不代替接口契约或板测 |

## FPGA 固定来源与采用记录

以下只参考结构和方法，自行编写本Skill；未复制、改编或执行这些仓库的脚本/技能正文，未将其RTL整包导入。许可栏是该次资料核查结果，不替代对未来实际复用文件的检查。

| 固定版本与来源 | 采用点 | 不采用点与许可记录 |
|---|---|---|
| [FPGA-Agent vivado-tcl](https://github.com/Shinei-Nouzen-Arch/FPGA-Agent/blob/b60a52ea4d7498cd7e63ba72715c6eb3cf15ec66/vivado-tcl/SKILL.md)，`b60a52ea4d74` | 读取已有工程，区分脚本、执行和报告；按任务加载 | 不复制其模板或固定版本/器件；[GPL-2.0](https://github.com/Shinei-Nouzen-Arch/FPGA-Agent/blob/b60a52ea4d7498cd7e63ba72715c6eb3cf15ec66/LICENSE) |
| [Vivado-Automation-Skill](https://github.com/Aneein/Vivado-Automation-Skill/blob/3b63e73808b54bc17e87e56520af43aa73621b8c/SKILL.md)，`3b63e73808b5` | 由用户目标核对IP、时钟、复位、接口与实际产物 | 不继承强制运行到bitstream、旧版迁移和特定目录规则；[MIT](https://github.com/Aneein/Vivado-Automation-Skill/blob/3b63e73808b54bc17e87e56520af43aa73621b8c/LICENSE) |
| [ESnet manage_ip.tcl](https://github.com/ESnet/esnet-fpga-library/blob/201ed5c4f941b6af23d696961e7e3020bdab52e4/scripts/vivado/manage_ip.tcl)，`201ed5c4f941` | IP配置源、生成产物、仿真与综合阶段分离 | 不引入Make/命名体系，不将其禁止BD脚本source的项目规则推广；[带附加条款的BSD风格原文](https://github.com/ESnet/esnet-fpga-library/blob/201ed5c4f941b6af23d696961e7e3020bdab52e4/LICENSE.md)，API为NOASSERTION |
| [Digilent vivado-library](https://github.com/Digilent/vivado-library/tree/f4613fff005b098065fd5d619a2b88e55720a423)，`f4613fff005b` | 可复用接口IP与用户wrapper分工 | 不推定支持完整HDMI或任意器件/引脚。根[MIT](https://github.com/Digilent/vivado-library/blob/f4613fff005b098065fd5d619a2b88e55720a423/License.txt)，实际[dvi2rgb.vhd](https://github.com/Digilent/vivado-library/blob/f4613fff005b098065fd5d619a2b88e55720a423/ip/dvi2rgb/src/dvi2rgb.vhd)另有BSD-3-Clause文件头；本次不导入RTL |
| [PULP common_cells](https://github.com/pulp-platform/common_cells/tree/e73baaec2ca665cd80c3c384e9258e35242b829c)，`e73baaec2ca6` | 通用模块、manifest依赖及复位/CDC契约的检查方法 | 不单文件盲拷，不把所有CDC当作任意独立复位可用；[Solderpad 0.51](https://github.com/pulp-platform/common_cells/blob/e73baaec2ca665cd80c3c384e9258e35242b829c/LICENSE)；具体契约见[cc_cdc_2phase](https://github.com/pulp-platform/common_cells/blob/e73baaec2ca665cd80c3c384e9258e35242b829c/src/cc_cdc_2phase.sv) |

后续AXI专项候选：[Taxi](https://github.com/fpganinja/taxi/tree/cc70b270b910d369ab1ad7b3855e76399fd461f1)（`cc70b270b910`，CERN-OHL-S-2.0/另行商业授权）与[原verilog-axi](https://github.com/alexforencich/verilog-axi/tree/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53)（`516bd5dadc33`，MIT、README已有弃用/迁移说明）。不自动换库，未来按接口、许可、迁移成本和对应模块证据评估。

未发现完整满足本项目“已有模块/厂商IP/XPM/开源/自研”选择规则的现成技能；选型规则是本交付的独立设计。固定提交仅用于可追溯，不是长期冻结所有项目版本的要求。

## v0.2 用户主导配置与扩展机制

核查日期：**2026-09-28**。以下指南独立编写；本地源代码读证用于核对实际版本，不将厂商源码纳入原创MIT内容。

| 来源 | 采用点与版本边界 |
|---|---|
| [ST UM1718 CubeMX](https://www.st.com/resource/en/user_manual/um1718-stm32cubemx-for-stm32-configuration-and-initialization-c-code-generation-stmicroelectronics.pdf) | 用户配置任务与对象，再生成框架；结合本机CubeMX 6.18.1模板核对对象、入口和栈单位，不把配置描述文件名当内核版本 |
| [FreeRTOS Static vs Dynamic](https://www.freertos.org/Documentation/02-Kernel/02-Kernel-features/09-Memory-management/03-Static-vs-Dynamic-memory-allocation) | 两种分配方式的实际含义及共存；不把C static、启动创建和全工程无堆混为一谈 |
| [Arm CMSIS线程属性](https://arm-software.github.io/CMSIS_6/main/RTOS2/group__CMSIS__RTOS__ThreadMgmt.html)、[CMSIS-FreeRTOS 11.2限制](https://arm-software.github.io/CMSIS-FreeRTOS/v11.2.0/page_technical_data.html) | 属性、存储与适配器依赖；本机G4 FW1.6.3所带旧适配器行为另外读证，不把11.2能力套入10.3.1源码 |
| [TouchGFX交互](https://support.touchgfx.com/docs/development/ui-development/designer-user-guide/interactions-view)、[多人协作](https://support.touchgfx.com/4.26/docs/development/ui-development/working-with-touchgfx/multiple-developers)、[构建](https://support.touchgfx.com/docs/development/ui-development/working-with-touchgfx/compiling-and-flashing) | 用户预设导航与交互、磁盘配置与Designer内存副本冲突、原生生成/模拟器构建；本机版本4.26.1，未由模拟器推断目标板显示性能 |
| [Zephyr Devicetree vs Kconfig](https://docs.zephyrproject.org/latest/build/dts/dt-vs-kconfig.html) | 陌生工具适配的声明源职责案例；仅作为资料与工程分析测试，不宣称已做Zephyr真实构建 |

用户设计约定和长期任务状态规则来自本轮协作需求与隔离验证方法，不引入第三方工作流框架；不自动写入全局规则或记忆。
