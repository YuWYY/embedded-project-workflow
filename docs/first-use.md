# 第一次使用：看懂工程，明确下一步

只读入口不需要CubeMX、TouchGFX、Vivado、编译器或开发板，使用已有Python 3.12即可。自己的工程可直接读取；下面的原创演练使用完整仓库，并从仓库根目录运行。这里不安装Skill、不生成、不编译，也不改工程；脚本将观察结果写到终端。

没有 Python 时，可以让 AI 直接读取下面的配置文件完成同一练习；不要将未运行脚本写成脚本验证通过。只有 Skill ZIP 时，可用其中的脚本读取自己的工程；本页演练材料需从完整仓库取得。包的区别见[README](../README.md)。

## 已有自己的工程

从自己的当前副本开始即可，不必先完成所有示例。在PowerShell中替换引号内路径；引号可保留中文及空格。这里只读配置，不自动执行工程声明的命令：

```powershell
python -B "<Skill目录>/scripts/project_intake.py" inspect --project "<当前工程副本的绝对路径>"
```

`<Skill目录>`在完整仓库中是`skills/embedded-project-workflow`，在Skill ZIP中是解压后的`embedded-project-workflow`。可将`--project`直接指向一个IOC、TouchGFX、XPR或BD文件；从目录读取且入口不明确时，增加`--entry "<目录内相对入口>"`。同目录IOC和TouchGFX不必二选一，先按目标核对它们的关系。

用[README的只读委托](../README.md#拿一个具体任务试用)让AI解释结果。最终应能指出当前根目录、入口、相关对象及单位、用户实现和构建接入，并给一个具体下一步。脚本只读有限配置字段，代码接入还需AI查看实际源码。没有自己的工程时，再选下面一个原创片段练习。

## 先选一个熟悉的方向

| 方向 | 真实入口 | 本次要找的对象 | 看完后应理解什么 |
|---|---|---|---|
| STM32 / RTOS | [FirstLook.ioc](../examples/first-use/cubemx/FirstLook.ioc) | `SampleFeed`、`StatsWorker`、`SampleQueue` | 任务名、入口、容量和分配方式保存在配置中；业务实现还需要另外接入 |
| TouchGFX | [FirstLook.touchgfx](../examples/first-use/touchgfx/FirstLook.touchgfx) | `StatisticsScreen`、`resetButton`、`resetStatistics` | 控件名、交互名和实际业务是不同层；有交互声明不等于已实现清空 |
| Vivado | [FirstLook.xpr](../examples/first-use/vivado/FirstLook.xpr) → [design_1.bd](../examples/first-use/vivado/design_1.bd) | `design_1`、`axi_gpio_0` | XPR 引用设计文件，BD 描述实例与连接；文件可读不证明 IP 已生成或软件能访问 |

这些是自写的最小阅读材料，**不是可交给厂商工具生成、构建或上板的完整工程**。字段中的芯片、版本、尺寸和容量只服务这个练习，不是工程推荐值。

## 运行一次只读检查

任选一条：

```powershell
python -B skills/embedded-project-workflow/scripts/project_intake.py inspect --project examples/first-use/cubemx
python -B skills/embedded-project-workflow/scripts/project_intake.py inspect --project examples/first-use/touchgfx
python -B skills/embedded-project-workflow/scripts/project_intake.py inspect --project examples/first-use/vivado
```

在终端核对本次根目录、入口和上表对象。脚本应分别说明观察到了什么、哪些来源缺失，以及哪些能力没有验证；识别到工具版本只代表源文件写了这个版本，不代表本机已安装。具体输出字段以 `--help` 和当前脚本为准。

若从同时含多个示例的父目录开始，可指定实际入口：

```powershell
python -B skills/embedded-project-workflow/scripts/project_intake.py inspect --project examples/first-use --entry touchgfx/FirstLook.touchgfx
```

`--entry` 选择当前根目录中的工程入口，不应使脚本读取另一个工作副本。需要机器读取结果时，在命令末尾加 `--format json`。终端输出不是另外一套工程配置，不需要把参数抄回任何文件。

## 让 AI 接着解释一个对象

下面以 TouchGFX 为例。替换仓库路径后，给 AI 发送：

```text
请读取 <仓库绝对路径>/skills/embedded-project-workflow/SKILL.md。
本轮只读查看 <仓库绝对路径>/examples/first-use/touchgfx，
入口是 FirstLook.touchgfx，不安装、不生成、不构建、不连接硬件。
我想理解 StatisticsScreen 的 resetButton：
请从当前文件指出它触发哪个交互、交互声明了什么动作，
以及为什么现在还不能说“点击已清空统计”。
只解释这个对象，指出下一步应去哪里找用户实现。
```

AI 应使用文件里真实存在的名字，区分对象与显示文字，并说明本例缺少用户 View/Presenter/Model 和运行证据。不要要求它证明不存在的完整业务，也不必为这个问题建立计划文件或让你重复填已有字段。

换成 STM32 时，可询问 `StatsWorker` 的创建入口与分配策略；换成 Vivado 时，可询问 XPR 如何引用 `design_1.bd`、其中声明了哪个 GPIO 实例。选择一个问题就足够完成第一次演练。

## 从概览继续一项小改动

先核对概览的根目录、当前入口和对象名。需要更具体的建议时，可继续委托：

```text
沿用刚才确认的工程和目标，给出一个最小改动建议：
指出真实对象或文件、保留哪些约定、怎样观察结果，以及现在缺少什么条件。
已有事实直接复用；本轮仍只读，不启动工具或修改文件。
```

没有功能目标时，下一步可以是找到一个对象的实际实现。需要实施时，再使用README的“接入功能”委托明确目标与允许范围；已经授权的任务不必为每个相关文件重复确认。

| 当前读到了什么 | 可以接着做什么 |
|---|---|
| 配置可读，用户实现尚未找到 | 沿实际入口查相关源码和构建引用，说明缺口；不把声明当功能完成 |
| 局部可读、缺引用或格式未覆盖 | 保留已知事实，指出声明的缺失路径或未读字段，继续相应的原生文件分析 |
| 工具/版本不在窄脚本范围 | 说明该脚本未覆盖，按现有工具核查可行操作；不判整个工程无效或绕过检查 |
| 已有完整工程且满足窄入口条件 | 按[包内最小调用](../skills/embedded-project-workflow/references/execution-entries.md)核对参数，再在授权范围内实施 |

CubeMX窄脚本只改既有栈/静态队列参数；TouchGFX窄脚本只生成/构建当前Simulator，按钮业务仍需接入；SoC脚本检查已有BD/XSA/SDT，不生成缺少的交接文件。只读入口给出的执行器提示不代表已具备执行条件。TouchGFX执行器另有限制：工程路径中的空格不能靠命令引号解除，遇到时保留当前工程并分析可行路径，不擅自搬动原件。

需要你点界面时，让AI一次给出“打开哪份工程 → 找哪个真实对象 → 做什么 → 应看到什么”。保存后由AI重读磁盘变化，再接续相关用户代码和验证。概览、生成、构建与实际行为分别报告，不因上一阶段通过就宣布后续完成。

本候选的代理预验和真人试用分别记在[支持表](support.md)。本页的“应看到”是演练预期，不等于已经取得真人反馈；先完成代理预验，再邀请真人使用，真人尚未参与不会阻塞候选的独立验证。

## 尚待开展的首次真人试用

参与者使用自己的工程副本，从上面的三个入口中选一个：先说明一个小目标、哪些结构已确定、允许AI操作到哪一步。AI从当前文件提取其余已有信息，不要求先填写完整参数表。

完成一项可观察行为后，参与者在原工具保存一次小配置变化，再让新会话仅凭当前工程和短交接记录继续。反馈只需说明：是否顺利开始、是否问了已回答的问题、是否保留修改、能否继续用原工具维护，以及哪一步需要人额外解释。生成、编译、界面操作和板上行为分别记录。

本轮没有外部参与者或真人反馈；以上是待用试用步骤，不是已经完成的体验结果。
