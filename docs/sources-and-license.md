# 来源与许可边界

本仓库的 Skill、维护脚本、原创 RTL wrapper、测试平台和 Tcl 为独立编写，适用仓库根目录 [MIT License](../LICENSE)，署名 YuWYY。参考既有协作方法与官方工具机制，不整包导入第三方 Skill、构建系统或 RTL 库。

[Skill 来源记录](../skills/embedded-project-workflow/references/sources.md) 保留核查日期、来源、固定版本（已核查的 FPGA 来源）、采用点与未采用点。记录属于当时版本的核查结果，不保证远端未来内容不变；未固定的历史 STM32 分支链接在该记录中明确标注。

| 参考来源 | 记录的许可与边界 |
|---|---|
| ByTaymur 的 STM32 workflow | MIT；借鉴组织方法，不复制文本和模板 |
| NUEDC-STM32-MSPM0-SKILL | 当时未发现明确许可；仅参考思路，不分发其内容 |
| MaJerle CubeMX/CMake workflow | 只参考生成与用户内容分离的方法，不引入脚本 |
| FPGA-Agent | GPL-2.0；仅参考结构，不复制 Skill 正文 |
| Vivado-Automation-Skill | MIT；只参考方法，不采用默认运行到 bitstream 的要求 |
| ESnet FPGA library | 按固定提交的附加条款 BSD 风格原文记录；不引入代码 |
| Digilent vivado-library | 根 MIT，部分模块另有 BSD-3-Clause 文件头；本仓库未导入模块 |
| PULP common_cells | Solderpad 0.51；用于检查依赖及复位契约的方法，不导入 RTL |

STM32CubeMX、TouchGFX、Vivado、XSim、Clocking Wizard 和 XPM 均是外部工具或厂商内容。用户使用自有工具安装生成所需产物；这些工具、库、生成物以及相应许可不由本仓库 MIT 重新授权。Vivado 示例只分发独立编写的集成代码与测试，运行时引用本机厂商实现。

v0.2 新增的 CubeMX `.ioc`、APP 实现和重建脚本、TouchGFX 设计文件及用户 Model/View/Presenter、10 个合成评估输入与准备脚本均为本项目原创，适用 MIT。它们不附带 STM32 HAL、CMSIS/FreeRTOS 内核、TouchGFX framework/库/字体/模板包、Vivado IP 输出产品或仿真模型。工具生成的工程仅保留在使用者指定的本地隔离目录，依赖与版本见各示例 README。

TouchGFX 示例使用者须已有合法可用的本地安装和 Simulator 模板；重建脚本从本地模板创建工程，不能从本仓库获得厂商实现。CubeMX 示例同样依赖本地固件包、器件包及编译器，不自动下载。公开的验证 JSON 是删除个人路径和原始日志后的结果摘要，源码哈希用于区分完整执行版本与后续定向修订。

历史私有工程、CSV、原始对话、原始工具日志和固件不属于公开交付。公开验证说明是整理后的观察，不能用来重建未公开的私有案例。新增10例可由仓库准备输入，历史16例未整体公开，两者不可混称为26例完全公开的基准。未来若实际复用第三方代码，应按对应文件和版本增加许可证与署名，不由本文的思想参考自动推导复制授权。
