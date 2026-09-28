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

历史私有工程、CSV、原始对话、原始工具日志和固件不属于公开交付。公开验证说明是整理后的观察，不能用来重建未公开的私有案例。未来若实际复用第三方代码，应按对应文件和版本增加许可证与署名，不由本文的思想参考自动推导复制授权。
