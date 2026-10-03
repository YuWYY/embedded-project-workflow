# 嵌入式与 FPGA 工程协作

`embedded-project-workflow` 帮助 AI 读取你的工程和目标，选择原生配置、已有组件或用户代码，在约定范围内完成实现，让你继续用熟悉的工具维护工程。

**v0.7.0-beta.1 公开预览版**聚焦从自己的工程读出概览、选定下一步并接续一项改动。下载与发布状态见[本版本 Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.7.0-beta.1)，当前提交检查见[CI](https://github.com/YuWYY/embedded-project-workflow/actions/workflows/validate.yml)，实际验证范围见[支持与证据](docs/support.md)。预览版保留已知限制，历史通过结果不自动证明新版本通过。

| 从这里开始 | 你会得到什么 |
|---|---|
| **先看懂我的工程** · [无需厂商工具的入门](docs/first-use.md) | 配置源、相关对象、用户代码与构建接入，并给一个具体下一步；不改变工程 |
| **在已有结构中加功能** · [接手指南](skills/embedded-project-workflow/references/existing-projects.md) | 沿用任务、页面或接口完成一个明确行为，交付相关修改与真实验证 |
| **我改过配置，请继续** · [续接指南](skills/embedded-project-workflow/references/long-project-workflow.md) | 保护最新设计，调整受影响接入，指出哪些旧验证已经失效 |

## 拿一个具体任务试用

第一次接触时，建议下载下方的完整源码 ZIP 并解压，再选择一条委托，替换尖括号中的路径及任务。没有自己的工程时，先做上面的原创只读演练；有工程时从当前工作副本开始。当前能执行到哪一步见[支持范围](docs/support.md)。

`<SKILL.md绝对路径>`：完整源码包中是 `<仓库绝对路径>/skills/embedded-project-workflow/SKILL.md`；Skill ZIP 中是 `<解压目录绝对路径>/embedded-project-workflow/SKILL.md`。请让 AI 显式读取实际文件，不必先安装 Skill。只读脚本需要已有 Python 3.12，入门不需要厂商工具；没有 Python 时也可让 AI 直接阅读配置，不能因此声称脚本已运行。

**1. 只读看懂。** 最少输入是工程位置与想了解的对象或目标；预期得到有来源、单位和缺口的简短概览，以及一个可继续的动作。

```text
请显式读取 <SKILL.md绝对路径>。
只读查看 <工程绝对路径>，我想了解 <对象或目标>。
说明原生配置、用户代码、构建入口及缺口；不修改、不生成、不连接硬件。
已有信息请从工程读取，只追问会影响设计的缺口。
最后给一个下一步：在哪个真实对象或文件做什么、预期看到什么、还缺什么条件。
```

**2. 接入功能。** 最少输入是工作副本、目标行为和要保留的结构；预期得到相关实现、接入检查以及已执行/未执行的验证。

```text
请显式读取 <SKILL.md绝对路径>。
在 <工作副本绝对路径> 的 <现有对象或功能链> 中实现 <一个目标行为>，
保留 <当前接口、职责或其他明确约定>。允许在此副本内修改、使用已有工具生成和离线构建；
范围内直接推进，不安装软件、不连接硬件。请核对实际入口和行为。
```

**3. 接续人工配置。** 最少输入是当前副本、已保存的配置入口和本次改动；预期保留新设计、修正用户层引用并重验受影响部分。

```text
请显式读取 <SKILL.md绝对路径>。
继续 <当前工作副本绝对路径>。我已保存 <配置文件>，把 <旧对象/交互> 改为
<新对象/交互>。以磁盘当前设计为准，保持原有行为，只调整相关用户代码与
接入；允许已有工具离线生成构建，不安装、不连接硬件。说明旧验证哪些失效。
```

授权持续有效，正常相关改动无需逐文件确认；确需改变明确约定时，AI 应给出原因、最小改动和影响。

不必填满参数表。可选一个已有功能链，例如沿RTOS采样队列加统计、接通Designer新增按钮，或调整允许范围内的IP参数。脚本只覆盖各自声明的检查或生成构建，实际业务仍需接入；[包内最小调用](skills/embedded-project-workflow/references/execution-entries.md)说明参数从哪里读取和何时可用。

## 下载哪一份

| 获取方式 | 包含什么 | 适合谁 |
|---|---|---|
| **[完整源码 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/embedded-project-workflow-source-v0.7.0-beta.1.zip)** | Skill、指南、检查脚本、原创示例、入门材料和评估输入 | 第一次试用、查看案例和参与改进；本页的入门命令以此为准 |
| **[Skill ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/embedded-project-workflow-v0.7.0-beta.1.zip)** | `embedded-project-workflow/` 内的主入口、参考指南、脚本及许可 | 已有自己的工程，只需要把 Skill 交给 AI；不包含仓库的 `docs/`、`examples/`、`tests/` |
| **[Vivado 示例 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/vivado-examples-v0.7.0-beta.1.zip)** | 独立的原创 Vivado 案例源码及许可 | 按案例说明使用本机已有工具；它不是 Skill 包，也不含厂商依赖 |

下载或解压不会安装 Skill。未安装时使用真实 `SKILL.md` 路径，不假定 `$embedded-project-workflow` 已能解析。仅有 Skill ZIP 时，入口是 `<解压目录>/embedded-project-workflow/SKILL.md`；只读检查脚本也在该目录的 `scripts/` 下。三个包使用同一版本；校验值见 [SHA256SUMS.txt](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/SHA256SUMS.txt)。实际附件以[本版本 Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.7.0-beta.1)为准，发布流程见[发行说明](docs/releasing.md)，不用旧版附件代表新版。

## 怎样协作

**读取用途与当前设计 → 判断配置、组件和用户代码的分工 → 在授权范围内实施 → 验证真实接入 → 留下可维护的结果。**

| 你可以预设 | AI 在约定内接续 |
|---|---|
| 外设、引脚、时钟、DMA 和中断关系 | 给出有依据的配置建议，使用可用原生工具生成，接入应用 |
| 任务、队列、职责、容量与分配策略 | 沿现有对象实现业务，核对入口与存储语义 |
| 页面、控件、资源、导航与交互 | 在用户 View、Presenter、Model 接入动态行为，保护最新设计 |
| IP、接口、时钟域、板型与 PS/PL 分工 | 比较官方 IP、成熟模块和自写 RTL，核对连接及软硬件交接 |
| 可修改范围和本轮终点 | 完成相关验证，区分未执行与失败，必要时保留恢复位置 |

基础资源错误修回原生配置；应用工作参数可由用户层集中维护。每项参数分别明确来源、决定权和生效时点。小修改只处理相关部分，不强制完整访谈、任务数据库、全仓审计或每轮报告。

Skill 提供规则、参考资料和有限执行脚本；实际 GUI、生成、编译和硬件操作依赖本机能力及相应授权。脚本的窄范围不是所有工程的兼容承诺，也不妨碍 AI 依据当前工具继续分析。

## 按需继续阅读

- [主入口](skills/embedded-project-workflow/SKILL.md)、[配置约定](skills/embedded-project-workflow/references/configuration-contracts.md)、[长期任务恢复](skills/embedded-project-workflow/references/long-project-workflow.md)
- [CubeMX](skills/embedded-project-workflow/references/stm32-cubemx.md)、[FreeRTOS](skills/embedded-project-workflow/references/freertos.md)、[TouchGFX](skills/embedded-project-workflow/references/touchgfx.md)
- [板级依据](skills/embedded-project-workflow/references/board-evidence.md)、[Vivado](skills/embedded-project-workflow/references/vivado-workflow.md)、[Zynq/MPSoC](skills/embedded-project-workflow/references/zynq-mpsoc.md)、[Vitis 交接](skills/embedded-project-workflow/references/vitis-handoff.md)
- [功能接手案例](examples/feature-handoff/README.md)、[Vivado 案例](examples/vivado/README.md)、[ESP-IDF 资料与源码](examples/esp-idf/README.md)
- [v0.6参考调研与取舍](docs/research-v06.md)、[来源与许可](docs/sources-and-license.md)、[维护与发行](docs/releasing.md)

Vitis 平台/BSP/Arm 应用构建、ESP-IDF 原生构建等未覆盖事项见[支持表](docs/support.md)。构建与仿真不能替代板测；现有材料不证明统一的提效比例或故障率下降。

## 许可与反馈

原创 Skill、脚本、合成案例和用户实现采用 [MIT](LICENSE)，Copyright (c) 2026 YuWYY。厂商框架、库、模板、字体及第三方内容不随包重新授权。入门配置片段只用于阅读，不分发厂商工程生成物。

反馈请附版本/tag、工具版本、本次目标、实际行为和最小可公开材料。无需上传私有工程、凭据或注册日志。新用户真人体验会在代理预验后邀请；尚未收到真人反馈不改写已有代理验证结果，也不写成真人已验证。
