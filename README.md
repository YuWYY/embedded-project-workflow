# 嵌入式与 FPGA 工程协作

`embedded-project-workflow` 帮助 AI 根据用户目标，发现原生配置与组件能力，划分工具生成和用户代码，在用户约定内完成实现、验证及多阶段续接。用户可先配置工程，也可授权 AI 代配置，并继续用原工具维护结果。

本版为 **v0.5.0-beta.1 公开预览版**，汇集 v0.3～v0.5 的功能与验证。本轮增加板级资料匹配、Zynq/MPSoC原生设计和Vitis交接指南，制作窄的BD/XSA/SDT一致性检查与原创案例。当前实施状态和分层边界见[SoC交接说明](docs/soc-handoff.md)。[v0.4](docs/validation-v04.md)、[v0.3](docs/validation-v03.md)及更早记录保持为历史证据，不自动证明新源码通过。

专用指南覆盖 STM32CubeMX、FreeRTOS、TouchGFX、Vivado及Zynq/MPSoC交接；Vitis指南不等于Arm平台/BSP/应用已构建通过。ESP-IDF保留资料和源码案例，没有原生构建验证。陌生工具按当前工程与官方机制主动适配，并说明实际验证程度。采用显式读取试用，未安装、未启用自动调用。下载源码或压缩包不会安装 Skill。

## 工作方式

**读取用途与用户设计约定 → 识别原生配置/组件复用/自写代码 → 在授权范围内配置和生成 → 用户层实现 → 验证实际接入 → 保留可维护、可续接的结果。**

| 用户可以预设 | AI 在约定内负责 |
|---|---|
| 外设、中间件、引脚、时钟、DMA 和中断关系 | 推导必要建议，修改明确的配置源，真实生成并接入应用 |
| 任务、同步对象、职责、容量与内存策略 | 通过工具支持的对象骨架接入独立业务，不隐藏新增任务绕过约定 |
| 页面、控件、资源、导航与交互 | 保留 Designer 结构，在用户 View/Presenter/Model 中实现动态行为 |
| IP、接口、时钟域、连接和可调范围 | 比较成熟组件与自研，完成配置、RTL 适配及相应验证 |
| 板型、PS/PL职责、软件目标及维护来源 | 主动补齐相关板级依据，核对参考设计，配置BD/IP并检查XSA/SDT和软件交接 |
| 构建、存储布局和阶段验收条件 | 核对实际构建与证据，恢复时保护用户新改动 |

配置来源、决定权和生效时点分别明确。已有配置不自动全部冻结，授权范围内不逐文件询问；确需突破明确约束时提出有证据的具体方案。静态内存分配、C `static`、创建时机和设计期/运行期参数分别处理。

主入口按需加载指南。小修改不强制完整访谈、全仓审计、任务数据库或每轮新增报告。Skill 提供协作规则与资源；实际生成和执行需要本机工具及相应授权，不自动获得 GUI、硬件或后台常驻能力。

## 显式试用

把下列占位路径替换为你下载仓库后的绝对路径：

```text
请显式读取 <仓库绝对路径>/skills/embedded-project-workflow/SKILL.md。
本轮目标：……；工程与硬件资料：……；验收终点：……。
我已预设的结构和约束：……；允许你自主调整的范围：……。
允许在指定工作副本中代配置、生成、编程及运行相应离线验证。
先读取已有材料，自行判断工具配置、组件复用与用户代码的分工。
范围内直接推进；确需改变明确约定时给出原因、影响和最小方案。
保护我的最新配置，分阶段保留成功版本和续接信息；本轮不连接硬件。
```

不用为了套模板重复填写工程中已有的信息。合适的小任务包括：在预设任务中加入遥测；保留页面导航新增动态数值；调整已授权范围内的 IP 参数；在用户修改配置后继续生成；从项目状态记录恢复未完成任务。

板级与SoC委托可以写为：

```text
请显式读取这个仓库的Skill。我要在指定MPSoC工作副本中增加一个PL计数功能，
已有资料包含商品页面、核心板/底板版本、相关原理图和参考工程。
请先读取资料，缺少会影响设计的事实再问我；自主判断PS/PL、官方IP和用户RTL分工。
允许在副本中用原生工具配置、生成及离线验证，保留我从Vivado GUI维护BD的方式。
不要修改正式工程或连接硬件；交付时区分BD/XSA/SDT、软件构建和板测的实际状态。
```

人工修改后的接续可以写为：“我已在Vivado保存了新的外设地址，请读取当前BD，不运行旧创建脚本恢复配置；更新受影响的交接产物，说明软件平台是否也已更新，以及哪些验证尚未执行。”

未安装时，不假定 `$embedded-project-workflow` 能自动解析到本仓库。`agents/openai.yaml` 保留 `allow_implicit_invocation: false`；没有安装器或全局配置修改脚本。

## 指南与可重建材料

| 入口 | 内容 |
|---|---|
| [Skill 主入口](skills/embedded-project-workflow/SKILL.md) | 按需路由、配置与实现分工 |
| [用户设计约定](skills/embedded-project-workflow/references/configuration-contracts.md) | 主控边界、人工修改、陌生工具适配 |
| [长期任务](skills/embedded-project-workflow/references/long-project-workflow.md) | 阶段结果、证据身份、中断恢复 |
| [FreeRTOS 指南](skills/embedded-project-workflow/references/freertos.md) | 对象骨架、分配策略与真实入口 |
| [SoC支持矩阵与交接试用](docs/soc-handoff.md) | 板级依据、MPSoC硬件与软件元数据边界 |
| [v0.5验证记录](docs/validation-v05.md) | 本轮实际阶段、失败修订、来源身份与未覆盖事项 |
| [板级资料指南](skills/embedded-project-workflow/references/board-evidence.md) | 商品/原理图缺口、参考工程匹配和来源证据 |
| [Zynq/MPSoC指南](skills/embedded-project-workflow/references/zynq-mpsoc.md) | 自主架构、PS/PL、BD/IP及用户RTL分工 |
| [Vitis交接指南](skills/embedded-project-workflow/references/vitis-handoff.md) | XSA/SDT/平台/BSP与DMA、缓存、启动问题的诊断 |
| [v0.4支持与验收](docs/validation-v04.md) | 历史功能接入、结构接续及证据边界 |
| [既有工程接手](skills/embedded-project-workflow/references/existing-projects.md) | 有效来源、相关调用链与结构变更 |
| [功能接手案例](examples/feature-handoff/README.md) | 独立接手CubeMX/TouchGFX及共享业务模块 |
| [ESP-IDF](examples/esp-idf/README.md) | 官方机制与原创源码，原生构建未执行 |
| [验证说明](docs/validation.md) | 历史及本轮行为、工具证据与限制 |
| [Vivado 示例](examples/vivado/README.md) | Clocking Wizard、XPM FIFO，以及[用户约定与续接](examples/vivado/controlled-project/README.md) |
| [CubeMX / RTOS 示例](examples/cubemx-rtos/README.md) | 原创对象配置、再生成与链接负例 |
| [TouchGFX 示例](examples/touchgfx/README.md) | 两页面用户逻辑、人工配置变化与再生成 |
| [新增行为案例](evaluations/v02/README.md) | 可公开合成输入及复核方法 |
| [v0.4接手评估](evaluations/v04/README.md) | 设计约定、配置保护、脚本边界和当前证据 |
| [v0.5板级与SoC评估](evaluations/v05/README.md) | 13个原始案例、独立执行回答和定向行为复核 |
| [v0.3定向行为复验](evaluations/v03/README.md) | 授权内实施、人工修改、部分生成、中断续接与小修改 |
| [来源与许可](docs/sources-and-license.md) | 原创范围、第三方与厂商边界 |

实际结果按验证说明分层报告。模型回答、编译和仿真都不能替代板测；现有数据不证明降低多少故障率、节省多少额度或缩短多少开发时间。Zephyr 用于陌生工具资料与工程分析案例，没有声称已做真实 Zephyr 构建。

## 轻量检查与发行

结构和包检查只需 Python 3.12 标准库：

```text
python -B scripts/release.py validate
python -B scripts/release.py self-test
python -B scripts/release.py pack
python -B scripts/release.py verify-packages
```

GitHub Actions 运行上述检查，不安装厂商工具、不调用收费模型、不操作硬件。真实例子需要用户已有的厂商工具；脚本拒绝覆盖非空构建目录，完整原始日志留在本地。Skill 与 Vivado ZIP 沿用独立打包；CubeMX、TouchGFX、ESP-IDF和共用模块源例子从仓库获取。详见[发行说明](docs/releasing.md)。

## English overview

A task-scoped Codex skill for user-directed embedded and FPGA engineering. Match board evidence and reference designs, choose native configuration, reusable IP and user code, preserve editable project structure, and verify cross-tool handoffs. Guides cover STM32CubeMX, FreeRTOS, TouchGFX, Vivado and Zynq/MPSoC hardware-to-software metadata; Vitis platform/BSP/Arm application builds remain unverified in this preview release. ESP-IDF remains documentation/source-only. Unfamiliar tools require version-specific research and evidence. This beta remains explicit-only and does not install itself.

## 许可与反馈

原创 Skill、脚本、合成案例和用户实现采用 [MIT](LICENSE)，Copyright (c) 2026 YuWYY。厂商软件、库、模板、字体及第三方内容不随包重新授权。示例依赖本机已有安装，不分发厂商框架和生成物。

反馈请提供版本、工具、任务终点、用户约定、实际行为及最小可公开案例。无需上传私有固件、凭据或注册日志；后续修订围绕可复现问题进行。
