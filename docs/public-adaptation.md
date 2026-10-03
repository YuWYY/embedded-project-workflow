> 历史适配输入与 v0.6 结果保留在下文。v0.7 对同一旧 BD 的窄兼容结果见[当前验证](validation-v07.md)，未扩大原生执行范围。

# 两个公开工程的只读接手观察

2026-10-03 使用本候选的 `project_intake.py` 读取固定提交中的原生配置。只获取下表所列配置及仓库 README、许可文件；**没有克隆完整工程、启动第三方脚本或厂商工具，也没有生成、构建或连接硬件**。第三方原文和带本机路径的原始输出留在本地验证目录，不进入发行包。

本页记录真实的部分识别与范围缺口，不将任一结果表述为这两个工程已经获得原生支持。

## 固定输入与当前结果

| 上游及固定提交 | 读取输入 | 本次实际结果 |
|---|---|---|
| [arona-jkb/OPEN-MCU-UI](https://github.com/arona-jkb/OPEN-MCU-UI/tree/2c08e5dfd7ddc237dfd61440dfc9d45705c19e1d) · `2c08e5dfd7ddc237dfd61440dfc9d45705c19e1d` | `GUI_demo.ioc` | `PARTIAL`，进程退出 0。能够读取稳定字段；CubeMX 6.15.0 不在已有窄执行器的已验证版本范围 |
| [Halolo/ebaz4205-vivado](https://github.com/Halolo/ebaz4205-vivado/tree/5e30b8133ac1fd3f06950fa8146f0e8a4be43fc4) · `5e30b8133ac1fd3f06950fa8146f0e8a4be43fc4` | `addr-led.xpr` 及其引用的 `addr-led.srcs/sources_1/bd/ebaz4205/ebaz4205.bd` | 汇总 `ERROR`，进程退出 1；XPR 事实保留为 `PARTIAL`，BD 为 `ERROR`。当前解析器拒绝重复 JSON 键，不能据此判定上游工程错误 |

状态解释：`PARTIAL` 不等于生成或构建通过；`ERROR` 在这里表示本入口未完成声明的读取，不是厂商校验结果。两次读取前后的已下载文件清单及 SHA256 均保持相同。

## 读到了什么，还不能做什么

**STM32 工程。** IOC 声明 STM32F103C8T6、LQFP48、CubeMX 6.15.0、F1 固件 1.8.6 和 CMake；外设列表包含 DMA、NVIC、RCC、SPI1、SYS、TIM1。无需安装 CubeMX 即可报告这些原文事实。当前没有识别到受支持表形态的 RTOS 对象，这不能推断完整源码没有用户自建任务。脚本返回 `declared_metadata_match=false` 与 `execution_eligibility=NOT_CHECKED`；它没有把 F1/CMake 工程套用到 G474/ARMCC 窄适配器。

**Vivado 工程。** XPR 声明器件 `xc7z010clg400-1`、顶层 `ebaz4205_wrapper` 和多个 fileset，并能将 `$PSRCDIR` 解析到已下载 BD。XPR 中旧的工程位置只作为历史字段报告，没有用于跳转或读取旧位置。`Version=7`、`Minor=54` 是 XPR 格式字段，不作为 Vivado 产品版本。

BD 原文同一对象出现多个不同内容的 `address_block`，包括 `segment1`、`segment2`、`M_AXI_GP0` 等。当前 JSON 读取器要求对象键唯一，返回 `DUPLICATE_KEY: address_block`，没有采用后值覆盖前值，也没有伪造完整的 BD 实例或地址分析。这是明确的**解析范围不足**；没有运行 Vivado，无法把这一读取限制解释成原生工程无效。

XPR 还引用生成的 wrapper 和约束文件。本次有意只下载 XPR/BD 等有限文件，因此报告这两个引用为 `MISSING_REFERENCE`；**这不表示完整上游仓库缺失相应源码，也不表示正常生成后不会产生 wrapper**。只读入口没有尝试下载依赖或用旧产物补齐。

## 来源身份

| 原生文件 | SHA256 |
|---|---|
| `OPEN-MCU-UI/GUI_demo.ioc` | `9b62c49f99ae5a9826c0393679a08cde448bd86f6231c7f2bdd0808ecafa8aa6` |
| `ebaz4205-vivado/addr-led.xpr` | `477d0d0704560c9996ae170433073f9ec3bd8ac09846da9dcc5996414cb76273` |
| `ebaz4205-vivado/addr-led.srcs/sources_1/bd/ebaz4205/ebaz4205.bd` | `aec3e5645df0b77de88d24377637c5a0fe20eab699a264cae13cfc74bf313dc5` |

原始 JSON、文本、实际退出码、执行器源码哈希及前后输入清单分别保留在本地验证材料中。结果只支持“无需厂商环境读取部分原生事实，并指出不能解析的部分”，不支持自动修改、再生成、工具兼容、板级正确或效率提升的结论。

使用方法见[第一次使用](first-use.md)，当前支持状态见[支持与证据](support.md)。
