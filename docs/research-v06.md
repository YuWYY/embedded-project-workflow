# v0.6 参考项目调查与采用边界

核查日期：**2026-10-03**。本轮联合检索按“作者/仓库”去重，共 **32 个候选项目，15 个深读项目**。候选包括Skills、技能模板、标准及相邻工程工具，不称为32个同类Skill。深读指读取实际README以及相关SKILL、指南、模板或脚本；浏览只完成候选定位与范围筛选。数量描述调查范围，不是质量、兼容性或运行通过率。

以下为调查清单，不是安装清单。没有安装、运行或整包移植这些第三方项目；新增内容独立编写。外部项目的成功声明和示例参数不充作本项目验证，也不声称本项目独有这些方法。

## 去重清单

| 编号 | 作者项目 | 类型 | 阅读深度 |
|---|---|---|---|
| 1 | [anthropics/skills](https://github.com/anthropics/skills) | Skill 创建与评估 | 深读 |
| 2 | [obra/superpowers](https://github.com/obra/superpowers) | 开发方法与技能评估 | 深读 |
| 3 | [github/spec-kit](https://github.com/github/spec-kit) | 规格驱动工具与技能模板 | 深读 |
| 4 | [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | 增量规格与接续工具 | 深读 |
| 5 | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 文件化计划与恢复 | 深读 |
| 6 | [agentskills/agentskills](https://github.com/agentskills/agentskills) | 标准、文档与参考校验器 | 深读 |
| 7 | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | 上下文与评估方法 | 深读 |
| 8 | [openai/skills](https://github.com/openai/skills) | 技能目录与创作规范 | 浏览 |
| 9 | [vercel-labs/skills](https://github.com/vercel-labs/skills) | 发现与分发工具 | 浏览 |
| 10 | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 领域技能与发行索引 | 浏览 |
| 11 | [getsentry/skills](https://github.com/getsentry/skills) | 团队开发技能与来源保留 | 浏览 |
| 12 | [microsoft/skills](https://github.com/microsoft/skills) | SDK技能与测试组织 | 浏览 |
| 13 | [huggingface/skills](https://github.com/huggingface/skills) | 领域CLI与工作流技能 | 浏览 |
| 14 | [trailofbits/skills](https://github.com/trailofbits/skills) | 审查、验证与专业技能 | 浏览 |
| 15 | [Aneein/Vivado-Automation-Skill](https://github.com/Aneein/Vivado-Automation-Skill) | Vivado自动化Skill | 深读 |
| 16 | [Shinei-Nouzen-Arch/FPGA-Agent](https://github.com/Shinei-Nouzen-Arch/FPGA-Agent) | FPGA/Vivado技能集合 | 深读 |
| 17 | [beriberikix/zephyr-agent-skills](https://github.com/beriberikix/zephyr-agent-skills) | Zephyr技能 | 深读 |
| 18 | [ezrover/ESP32-AI-Agent-Skill](https://github.com/ezrover/ESP32-AI-Agent-Skill) | ESP32技能 | 深读 |
| 19 | [rovinax/embedded-skills](https://github.com/rovinax/embedded-skills) | 嵌入式技能集合 | 深读 |
| 20 | [Seeed-Studio/reSpeaker_Clip](https://github.com/Seeed-Studio/reSpeaker_Clip) | 设备工程与代理材料 | 深读 |
| 21 | [zww666-creater/NUEDC-STM32-MSPM0-SKILL](https://github.com/zww666-creater/NUEDC-STM32-MSPM0-SKILL) | STM32/MSPM0竞赛技能 | 深读 |
| 22 | [michpro/kicad-tools](https://github.com/michpro/kicad-tools) | KiCad工具与代理材料 | 深读 |
| 23 | [ByTaymur/embedded-software-skills](https://github.com/ByTaymur/embedded-software-skills) | 嵌入式技能 | 浏览 |
| 24 | [ProfYangShengXu/bobanana5-embedded-kitset](https://github.com/ProfYangShengXu/bobanana5-embedded-kitset) | 嵌入式工具材料 | 浏览 |
| 25 | [liueggy/my_mini_skills](https://github.com/liueggy/my_mini_skills) | 个人技能集合 | 浏览 |
| 26 | [Mindrally/skills](https://github.com/Mindrally/skills) | 技能集合 | 浏览 |
| 27 | [magnus919/agent-skills](https://github.com/magnus919/agent-skills) | 技能集合 | 浏览 |
| 28 | [espressif/esp-dl](https://github.com/espressif/esp-dl) | 嵌入式组件项目 | 浏览 |
| 29 | [Potapovrg/kicad-skill](https://github.com/Potapovrg/kicad-skill) | KiCad技能 | 浏览 |
| 30 | [bretbouchard/kicad-agent](https://github.com/bretbouchard/kicad-agent) | KiCad代理项目 | 浏览 |
| 31 | [olofk/fusesoc](https://github.com/olofk/fusesoc) | 硬件包与构建工具，非Skill | 浏览 |
| 32 | [olofk/edalize](https://github.com/olofk/edalize) | EDA工具适配层，非Skill | 浏览 |

补充参考：[amd/skillscope](https://github.com/amd/skillscope)及[amd/skills](https://github.com/amd/skills)由另一轮补充调查读取，不计入上表32/15；本候选不依赖或引入其框架。结构、引用、路由和行为应分别验证，具体通过范围以本项目真实结果为准。

## 主要方法来源：固定版本

以下提交由GitHub作者仓库API核对，日期均为本轮核查日。链接固定到当时默认分支的提交；后续上游更新不自动进入本Skill。许可按对应文件读取，仓库API字段只能辅助判断。未固定的候选仅保留调查线索，不作为可直接复制的已核实来源。

| 来源及固定提交 | 本轮采用的方法 | 没有采用的部分 | 许可 |
|---|---|---|---|
| [Anthropic skill-creator](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md)，`8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` | 区分旧版、候选与无Skill；独立输入与评分；同时观察结果、时间和重复劳动 | 不整套移植评分器，不以缺失结果或目录存在判通过；不默认开启自动触发 | [该Skill Apache-2.0](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/LICENSE.txt)，根API许可为空不能覆盖子目录许可 |
| [Superpowers writing-skills](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/writing-skills/SKILL.md)，`8ca22dba9a94f28898bbce59f2537ff4d87c747d` | 从真实失败决定用条件、正向结构或边界约束；新上下文对照 | 不引入强制多级批准、逐任务完整TDD、固定重试次数或全局hooks | [MIT](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/LICENSE) |
| [Spec Kit clarify](https://github.com/github/spec-kit/blob/e1fa857a7f536b22760d48c1aa9ace41df0fd1dc/templates/commands/clarify.md)，`e1fa857a7f536b22760d48c1aa9ace41df0fd1dc` | 仅澄清会改变实现或验收的缺口；答案更新对应约定并消除冲突 | 不固定问答轮数，不要求所有任务创建规格和流程目录 | [MIT](https://github.com/github/spec-kit/blob/e1fa857a7f536b22760d48c1aa9ace41df0fd1dc/LICENSE) |
| [OpenSpec onboard](https://github.com/Fission-AI/OpenSpec/blob/2500d6da971336167548b53731a35b2127df35ac/src/core/templates/workflows/onboard.ts)，`2500d6da971336167548b53731a35b2127df35ac`；[verify-change](https://github.com/Fission-AI/OpenSpec/blob/2500d6da971336167548b53731a35b2127df35ac/src/core/templates/workflows/verify-change.ts) | 以小任务讲清真实入口与可见结果；新增、修改、删除、重命名分开核对 | 本轮先用无厂商工具的原创只读片段，不照搬文档四件套、CLI或演练耗时承诺；文件存在不等于验证完成 | [MIT](https://github.com/Fission-AI/OpenSpec/blob/2500d6da971336167548b53731a35b2127df35ac/LICENSE) |
| [planning-with-files](https://github.com/OthmanAdi/planning-with-files/blob/dab9d16fbd9314448b319d112e99f497d7638d89/skills/planning-with-files/SKILL.md)，`dab9d16fbd9314448b319d112e99f497d7638d89` | 显式任务/副本身份；恢复时读取实际差异；共享状态有明确维护者 | 不加三份强制文档、每两次工具即落盘、自动历史回放或后台续跑 | [MIT](https://github.com/OthmanAdi/planning-with-files/blob/dab9d16fbd9314448b319d112e99f497d7638d89/LICENSE) |
| [Agent Skills规范仓库](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379)，`69ef37e9424c0a7ea9dd2293b559e43ec8176379`；[validator](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/src/skills_ref/validator.py) | 元数据、主入口与按需资源分层；格式与行为分别验证 | 不以标准校验声称所有客户端可执行；不把特定宿主hooks混入通用入口 | [代码Apache-2.0](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/LICENSE)；[README说明文档CC-BY-4.0](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/README.md) |
| [Context Engineering context-compression](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/58b55a8921758d13453b440704fb1b5b208c0b0e/skills/context-compression/SKILL.md)，`58b55a8921758d13453b440704fb1b5b208c0b0e` | 用目标、产物、决定、下一步探针检查接续；衡量任务总成本 | 不照搬压缩比例、案例规模、默认阈值或宿主自动压缩机制 | [MIT](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/58b55a8921758d13453b440704fb1b5b208c0b0e/LICENSE) |

## 对本候选的具体作用

本轮聚焦已有能力更容易用，不增加新的平台承诺：

- README提供第一次只读体验、已有工程实施和当前支持表三个入口，说明完整仓库与Skill包的差别。
- 只读来源检查与固定厂商安装profile分开；能够读取配置，不代表有工具或已经生成。
- 精简重复规则；保护当前设计、来源身份、真实业务接入和硬件权限等关键边界保持。
- 增加多副本识别、增删改名接续与新手真实对象单步说明。
- 执行器异常终态、原有业务正负例与CI分层作为针对性工程修订；具体结果另见当前支持表。
- 先由独立代理使用公开入门材料预验，再邀请真人；真人未完成保持未执行，不把其当作候选独立工作阻塞。

按需加载、用户设计约定、授权内自主实施、长期记录、源码身份和人工配置保护在v0.5已存在，本轮做精简和可用性增强，不包装成首次发明。

## 外部材料的核验规则

获取外部Skill后，先确认作者、所读版本、许可和实际文件，再用对应版本官方资料或本机接口核对代码、命令、单位与字段。发现矛盾时保留缺口，不因“开源Skill推荐”继续执行。许可未查明的项目不复制文本或脚本；特定项目成功不能推出通用支持。

本轮未复制第三方脚本、模板或长篇正文。深读清单包含不同许可及许可未明确的项目，实际复用时须按具体文件再次确认；本表的MIT原创声明不重新许可第三方内容。文章和历史工程中的频率、容量、电流、板型、任务数、性能比例及等待时间均不写成通用默认值。

本轮原始36次对照及定向复测已完成，结果含说明遗漏与环境失败，没有证明统计提效。输入准备、结构检查、模型行为、主机业务、厂商工具及真人反馈分别记录；测试不以是否重复指南用语评分。当前结论以[支持与证据](support.md)为准。
