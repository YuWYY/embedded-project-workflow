# 嵌入式与 FPGA 工程协作

`embedded-project-workflow` 帮助 AI 根据用户目标，发现原生配置与组件能力，划分工具生成和用户代码，在用户约定内完成实现、验证及多阶段续接。用户可先配置工程，也可授权 AI 代配置，并继续用原工具维护结果。

本版为 **v0.2.0-beta.1 预览版**。26类行为复核及三类真实工具在声明层级完成验证；最终 Vivado 入口实际完成100→125 MHz、同频再生成和空目录重建。此前原生 Tcl 文件/通道异常仍未定位，未据此宣称稳定性或根因修复。详见[验证记录与局限](docs/validation.md)。

首批专用指南覆盖 STM32CubeMX、FreeRTOS、TouchGFX 和 Vivado；陌生工具按当前工程与官方机制主动适配，并说明实际验证程度。采用显式读取试用，未安装、未启用自动调用。下载源码或压缩包不会安装 Skill。

## 工作方式

**读取用途与用户设计约定 → 识别原生配置/组件复用/自写代码 → 在授权范围内配置和生成 → 用户层实现 → 验证实际接入 → 保留可维护、可续接的结果。**

| 用户可以预设 | AI 在约定内负责 |
|---|---|
| 外设、中间件、引脚、时钟、DMA 和中断关系 | 推导必要建议，修改明确的配置源，真实生成并接入应用 |
| 任务、同步对象、职责、容量与内存策略 | 通过工具支持的对象骨架接入独立业务，不隐藏新增任务绕过约定 |
| 页面、控件、资源、导航与交互 | 保留 Designer 结构，在用户 View/Presenter/Model 中实现动态行为 |
| IP、接口、时钟域、连接和可调范围 | 比较成熟组件与自研，完成配置、RTL 适配及相应验证 |
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

未安装时，不假定 `$embedded-project-workflow` 能自动解析到本仓库。`agents/openai.yaml` 保留 `allow_implicit_invocation: false`；没有安装器或全局配置修改脚本。

## 指南与可重建材料

| 入口 | 内容 |
|---|---|
| [Skill 主入口](skills/embedded-project-workflow/SKILL.md) | 按需路由、配置与实现分工 |
| [用户设计约定](skills/embedded-project-workflow/references/configuration-contracts.md) | 主控边界、人工修改、陌生工具适配 |
| [长期任务](skills/embedded-project-workflow/references/long-project-workflow.md) | 阶段结果、证据身份、中断恢复 |
| [FreeRTOS 指南](skills/embedded-project-workflow/references/freertos.md) | 对象骨架、分配策略与真实入口 |
| [验证说明](docs/validation.md) | 历史及本轮行为、工具证据与限制 |
| [Vivado 示例](examples/vivado/README.md) | Clocking Wizard、XPM FIFO，以及[用户约定与续接](examples/vivado/controlled-project/README.md) |
| [CubeMX / RTOS 示例](examples/cubemx-rtos/README.md) | 原创对象配置、再生成与链接负例 |
| [TouchGFX 示例](examples/touchgfx/README.md) | 两页面用户逻辑、人工配置变化与再生成 |
| [新增行为案例](evaluations/v02/README.md) | 可公开合成输入及复核方法 |
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

GitHub Actions 运行上述检查，不安装厂商工具、不调用收费模型、不操作硬件。真实例子需要用户已有的厂商工具；脚本拒绝覆盖非空构建目录，完整原始日志留在本地。Skill 与 Vivado ZIP 沿用独立发行；新增 CubeMX、TouchGFX 源例子从仓库获取。详见[发行说明](docs/releasing.md)。

## English overview

A task-scoped Codex skill for user-directed embedded and FPGA engineering. Discover native configuration and reusable components, preserve user-defined structure and interfaces, implement within delegated boundaries, verify generated/user integration, and resume multi-stage work from actual project state. Dedicated guides cover STM32CubeMX, FreeRTOS, TouchGFX, and Vivado; unfamiliar tools require version-specific research and evidence. This beta remains explicit-only and does not install itself.

## 许可与反馈

原创 Skill、脚本、合成案例和用户实现采用 [MIT](LICENSE)，Copyright (c) 2026 YuWYY。厂商软件、库、模板、字体及第三方内容不随包重新授权。示例依赖本机已有安装，不分发厂商框架和生成物。

反馈请提供版本、工具、任务终点、用户约定、实际行为及最小可公开案例。无需上传私有固件、凭据或注册日志；后续修订围绕可复现问题进行。
