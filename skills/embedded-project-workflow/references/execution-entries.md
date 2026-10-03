# 包内脚本的最小调用

需要调用脚本时只读对应小节。用已有Python，替换引号内占位符；路径用绝对路径，`--entry`除外。命令示例不授予执行权限；先依据任务授权、实际来源和脚本范围选入口，不安装软件或连接硬件。工具在盘、源文件声明匹配与本次执行通过分别核实。

| 当前需要 | 入口与最低条件 | 能得到什么 |
|---|---|---|
| 看懂原生配置 | `project_intake.py inspect`；IOC/TGFX/XPR/BD文件或目录 | 终端上的有限配置事实；不写文件、不运行声明命令 |
| 调整既有RTOS容量 | `cubemx_rtos.py`；受支持完整隔离工程及固定安装profile | 既有任务栈/静态队列参数计划、生成与Keil Rebuild；不添加业务 |
| 重建当前界面设计 | `touchgfx_project.py`；支持的Simulator工程及已有安装 | 生成、Simulator构建；不实现按钮业务、不启动GUI |
| 核对已有SoC交接 | `soc_handoff.py`；当前BD、XSA、SDT均已存在 | 独立目录中的元数据一致性报告；不生成或构建这些输入 |

参数由AI从本轮工程与已有环境信息提取。路径、目标、源码、对象名能查到时不交回用户填表；有多个有效入口才让用户选择。新参数值由任务目标与单位决定，不复制示例数值。无工具或范围不匹配时继续独立分析，给出一个可行下一步，保留原生阶段未执行；不修改检查器来绕过拒绝。

## 只读认识当前工程

```powershell
python -B "<Skill目录>/scripts/project_intake.py" inspect --project "<工程目录或原生文件>"
python -B "<Skill目录>/scripts/project_intake.py" inspect --project "<工程目录>" --entry "<目录内相对入口>" --format json
```

没有厂商安装仍可调用。返回局部观察时保留已知事实，按诊断查缺引用或范围；多个来源不自动选择主工程。同目录IOC与TouchGFX可以共存。识别到对象不证明其用户实现或构建接入存在。

## CubeMX：已有栈与静态队列

限Windows、CubeMX 6.18.1、G4 1.6.3、ST CMSIS-RTOS2、ARMCC 5.06 u7 build960、G4 DFP2.0.0、STM32G474RE及已声明工程形态。IOC提供对象名、栈words与队列元素数；UVPROJX提供target和实际编译源码。`--user-source`列全本轮工程的应用源码，多个文件重复提供该参数；安装位置从已有环境核对，不能从IOC版本推断。

下面PowerShell变量仅复用参数；`inspect`检查固定安装profile（含编译器版本查询），不是无工具的intake。范围匹配且已授权后才调用plan/apply。

```powershell
$epwCube = "<Skill目录>/scripts/cubemx_rtos.py"
$epwCubeArgs = @(
  "--project", "<隔离工程目录>", "--ioc", "<IOC文件>",
  "--uvprojx", "<UVPROJX文件>", "--target", "<实际target>",
  "--user-source", "<应用源码.c>",
  "--cubemx", "<STM32CubeMX.exe>", "--firmware", "<G4固件目录>",
  "--uv4", "<UV4.exe>", "--armcc", "<armcc.exe>", "--pack", "<DFP2.0.0目录>"
)
python -B $epwCube inspect @epwCubeArgs
python -B $epwCube plan @epwCubeArgs --task-stack "<已有任务名>=<新words>" --output "<工程外新计划.json>"
python -B $epwCube apply --plan "<同一计划.json>" --work-root "<已存在的隔离父目录>" --reports "<工程外新报告目录>" --timeout 360
python -B $epwCube verify --plan "<同一计划.json>" --reports "<本次apply报告目录>"
```

只改队列时将`--task-stack`换为`--queue-capacity "<已有静态队列名>=<新元素数>"`。计划输出父目录须存在；工程必须位于work-root内且不能等于它；报告与工程互不包含。计划绑定当前来源，人工变更后重新计划。`--timeout`可省略，默认每子进程360秒。新增线程、修改业务或验证运行栈水位不在此脚本能力内。

## TouchGFX：当前Simulator生成与构建

从当前工程定位唯一根级`.touchgfx`及用户`gui`，从已有安装定位TouchGFX根目录。范围为Windows / TouchGFX4.26.1 / Simulator2.0.0与脚本声明的布局；硬件工程不自动适用。

```powershell
python -B "<Skill目录>/scripts/touchgfx_project.py" inspect --project "<当前Simulator工程>" --touchgfx-root "<已有安装目录>"
python -B "<Skill目录>/scripts/touchgfx_project.py" build --project "<当前Simulator工程>" --touchgfx-root "<已有安装目录>" --reports "<新的报告目录>" --timeout 300
```

`inspect`不启动工具；`build`已含一次生成和干净构建，只需生成时改为`generate`。报告必须与工程同卷且与工程、安装目录互不包含。此执行器拒绝工程路径空格等字符，给命令加引号也不会解除限制；可保留只读分析，或在已获授权的独立副本中选择符合限制的路径，不搬动原工程。当前设计应先保存，不能用旧准备脚本回灌模板。按钮回调→View→Presenter→Model业务由用户代码实现和验证；Simulator构建成功不证明点击已产生目标行为。

## SoC：已有交接元数据

此处是检查器。范围为Vivado2025.1、MPSoC、单个双通道AXI GPIO等声明形态。从当前BD读取真实实例名；XSA和SDT必须来自本轮有效交接，不能沿用旧产物冒充新设计。只有XPR/BD时先用intake，下一步是定位已有交接材料或核对其原生生成条件，不要求用户伪造缺失文件。

```powershell
python -B "<Skill目录>/scripts/soc_handoff.py" inspect --bd "<当前BD>" --xsa "<当前XSA>" --sdt "<system-top.dts>" --instance "<实际GPIO实例>" --report-dir "<新报告目录>"
python -B "<Skill目录>/scripts/soc_handoff.py" verify --bd "<当前BD>" --xsa "<当前XSA>" --sdt "<system-top.dts>" --instance "<实际GPIO实例>" --record "<对应来源的inspect报告/result.json>" --expected-base "<本次预期地址>" --expected-range "<本次预期范围>" --report-dir "<另一个新报告目录>"
```

两个命令均不修改输入、不启动厂商工具，但会创建报告，目录须与输入和工具目录互不包含。`--record`及预期地址/范围可省略；填写时必须来自本次目标，记录只可用于同一来源。若需核查已有AMD2025.1安装，可用`doctor --tool-root "<AMD工具根目录>" --report-dir "<新报告目录>"`；doctor只读在盘资料，不能证明平台、BSP或应用可构建。生成、综合与Vitis构建另按当前原生机制及授权进行。
