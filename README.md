# 嵌入式与 FPGA 工程协作

`embedded-project-workflow` 是面向 STM32CubeMX、TouchGFX、Vivado 工程的 Codex Skill，帮助 AI 根据用途选择配置、工具生成、用户代码以及 IP 复用或自研的分工。

本仓库处于 **v0.1.0-beta.1 预发布阶段**。当前采用显式读取试用，未安装到技能目录，也未启用自动调用。下载源码或压缩包不会安装 Skill。

## 解决什么问题

- MCU 基础配置错误修回图形配置源；PWM 频率、死区等应用参数集中在用户层，并核对采样和控制时序。
- 工具生成基础代码后，在受支持的保留区或独立 APP/BSP、View/Presenter/Model 等用户文件中扩展；再生成后同时检查调用链与编译接入。
- FPGA 模块先比较已有实现、厂商 IP/XPM、开源和自研；简单逻辑可直接写 RTL，学习与移植目标优先。
- 区分 FPGA 静态设计参数与真正运行时寄存器；配置源、生成产物和用户 wrapper 各有明确归属。
- 保存成功基线，优先解释首个故障；只增加能区分候选原因的测量，分别报告源码、构建、仿真和板测证据。

主入口很短，按当前任务读取对应指南。普通小修改无需完整访谈、全仓审计或每轮新增报告。

## 显式试用

将下列路径替换成你下载仓库后的实际绝对路径，向 Codex 提供：

```text
请显式读取 <仓库绝对路径>/skills/embedded-project-workflow/SKILL.md。
本轮任务是：在隔离副本中重新生成 CubeMX 工程，检查用户代码与构建接入。
先核对现有材料，只询问会影响本轮设计的缺失信息。
只修改指定工作副本，不连接硬件。分别报告生成、构建与未验证事项。
```

其他合适的小任务：调整已成功工程的 PWM 频率、TouchGFX 增加动态数值、选择异步 FIFO、修改 Vivado IP 的静态宽度或深度。提供工程位置、当前成功状态和本轮终点即可，不必预先填写全部外设参数。

未安装时，不假定 `$embedded-project-workflow` 能自动解析到这个仓库。`agents/openai.yaml` 的 `allow_implicit_invocation: false` 保留显式使用意图；本仓库没有安装器或全局配置修改脚本。

## 内容与验证

| 入口 | 内容 |
|---|---|
| [Skill 主入口](skills/embedded-project-workflow/SKILL.md) | 配置责任、按需路由、实现与调试原则 |
| [来源与许可](docs/sources-and-license.md) | 原创范围、固定来源及采用边界 |
| [验证说明](docs/validation.md) | 行为案例、真实工具证据与限制 |
| [Vivado 示例](examples/vivado/README.md) | Clocking Wizard、XPM FIFO 的可重建小工程 |
| [发布与校验](docs/releasing.md) | 独立文件清单、包验证及本地负例测试 |

历史评估中 16 类案例达到关键行为要求；两个旧版/新版成对案例均通过，不能据此证明新版更节省额度或降低故障率。实际 Vivado 2025.1 生成、XSim 与综合已经完成，本轮公开入口另有完整五阶段执行及 Windows PATH 选择修复的针对性验证。

真实 STM32/CubeMX 隔离试用已完成：经历配套工程文件缺失和生成覆盖导致的失败，修复配置及构建所有权后，连续两次完整生成保持关键接入，最终主机回归与干净构建通过。两项针对本次规则修订的合成案例复核通过；未对全部16类历史案例重新评估。原工程及旧 Skill 材料哈希不变。完整失败过程、证据层级及限制见[验证说明](docs/validation.md)；未进行硬件下载或板测。

轻量检查只需要 Python 3.12 标准库：

```powershell
python -B scripts/release.py validate
python -B scripts/release.py self-test
python -B scripts/release.py pack
python -B scripts/release.py verify-packages
```

GitHub Actions 执行这些检查，不安装厂商工具、不调用收费模型，也不把结构检查称为行为评估。真实 Vivado 示例需要用户已有的 Vivado 2025.1，运行方式见示例目录。

## English overview

A task-scoped Codex skill for embedded and FPGA projects: configuration ownership, generated/user code boundaries, IP selection, incremental debugging, and evidence-based reporting. Initial adapters cover STM32CubeMX, TouchGFX, and Vivado. Read `SKILL.md` explicitly from your local checkout; this beta does not install or enable automatic invocation. Existing evaluations are case observations, not proof of lower failure rates or token cost.

## 许可与反馈

原创 Skill、脚本和示例采用 [MIT](LICENSE)，Copyright (c) 2026 YuWYY。厂商软件和引用的第三方仓库不包含在授权范围内，也不打包随附。参见[详细边界](docs/sources-and-license.md)。

请通过任务反馈模板提供版本、工具、任务终点、实际行为和最小可公开案例。私有固件、设备凭据与原始注册日志不需要上传。后续规则只围绕可复现的问题修订。
