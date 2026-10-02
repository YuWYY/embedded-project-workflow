# Vivado 可重建验证示例

原创 Tcl、RTL、测试平台及 Python 入口采用仓库根目录 MIT 许可。AMD IP 与 XPM 从本机 Vivado 安装读取，未随仓库分发；其许可仍由 AMD 提供。下述时钟/FIFO入口需要 Windows、Python 3.10+、Vivado 2025.1、Artix-7 `xc7a200tfbg484-2` 器件支持、Clocking Wizard 6.0 与 XSim。器件与参数仅用于各自案例。

v0.5 增加独立的 [MPSoC/GPIO 交接案例](soc-handoff/README.md)，使用 ZCU102/MPSoC、BD、XSA 和 SDT。它有自己的依赖、入口和验证边界，不运行下述 Artix-7 流程，也不要求已有 A53 软件编译环境。该案例的本地说明同时列出分层证据与未覆盖事项。

在仓库根目录运行：

```powershell
# Vivado 已在 PATH 时：
python -B examples/vivado/scripts/rebuild.py

# 否则传入实际安装位置；<...> 是需要替换的占位符：
python -B examples/vivado/scripts/rebuild.py --vivado "<Vivado安装目录>/bin/vivado.bat" --build-root "<空的ASCII构建目录>"
```

若下载的是独立 Vivado ZIP，解压后先进入 `vivado` 目录，使用 `python -B scripts/rebuild.py`；需要时同样追加 `--vivado` 和 `--build-root` 参数。

不指定构建目录时使用 `tempfile` 新建目录。工具需要 ASCII 构建路径；如果系统临时目录包含中文，请通过 `--build-root` 指定新的 ASCII 目录。入口拒绝非空目录，将源码复制到构建目录后执行；不会删除旧构建、连接硬件或使用既有工程。安装路径通过参数或 PATH 查找，不内置机器路径。

v0.2另有[用户设计约定与续接示例](controlled-project/README.md)：将唯一时钟配置、接口约定和阶段证据分开维护，支持本例既有隔离工程的显式再生成。它复用本目录的时钟源文件，使用独立入口，不改变下述五阶段入口或FIFO实现。

## 实际执行的五个阶段

| 阶段 | 内容与检查 |
|---|---|
| `clock100` | 从 50 MHz 输入生成 100 MHz Clocking Wizard；用户 RTL 实现异步置位、输出域同步释放；XSim 检查 400 个输出周期、两次复位；IP OOC 与顶层综合 |
| `clock125_regenerated` | 在同一配置源上改为 125 MHz，再生成，并重置受影响综合 run；重复仿真和综合 |
| `clock125_clean` | 从空工程重建 125 MHz；重复验证，并比较再生成与干净重建 XCI 的配置语义 |
| `fifo_positive` | 实例化 16 位、512 深度 XPM 异步 FIFO，写/读时钟 80/100 MHz；独立参考队列检查满空、暂停、连续流量、按契约复位，随后综合 |
| `fifo_negative` | 注入固定数据位错误，必须被同一个检查器报告为数据不一致；只接受这一指定原因，不把编译失败当作成功 |

FIFO 正例预期为接受 3600、输出 3500、复位丢弃 100、最后待输出 0；测试覆盖满、空和背压。XPM 的内部实现没有被复制进测试平台。所有阶段都核对包内源文件与构建副本哈希。

## 输出与证据边界

控制台打印构建路径。`summary.json` 保存实际阶段结果、工具版本、源文件哈希、仿真计数、配置语义比较及最终状态。`execution_ledger.json`、每阶段 stdout、工程内日志和 `stage-results/` 报告保留在构建目录，可能含本机路径，不应直接上传。

每个 Tcl 要求 Vivado 2025.1；缺少器件或 IP 时会失败并保留原始日志。Python 返回码 0 仅表示五个阶段完成，包含预期被发现的负例。CDC、综合时序、资源、有效约束等报告需结合接口查看；报告存在不等于完整板级时序收敛。没有通过添加宽泛异步时钟例外来消除报告。

本示例不执行布局布线、bitstream、下载或板测，也不证明模拟电气特性或任意时钟比下的完整覆盖。时钟输入输出引脚、电气标准及完整板级 I/O 时序必须由具体工程提供。

已知报告项包括：时钟 IP 与用户 XDC 同时定义相同 50 MHz 输入时钟；XSim 向 `glbl` 传递其未声明的测试参数；XPM 内未使用逻辑被优化。应检查真实结果和相关约束，不以“警告全部清零”为目标。固定 80/100 MHz 时钟相位、两次确定性复位及一种数据错误注入不能替代随机相位、复位或失钟验证。FWFT 输出级可能使接口可观测待处理数超过配置的 RAM 深度，不能把两种计数含义混用。

## 本次公开入口验证

2026-09-28 的[五阶段真实结果](validation-20260928.json)记录了全部生成、仿真、综合和负例检查，使用显式 `--vivado` 路径完成。随后发现安装目录中的无扩展名 `vivado` 是 Unix 脚本，修正了 Windows PATH 查找顺序，优先 `.bat`／`.exe`。这是入口的一行修改，RTL、Tcl、TB 均未变化。

[后续 PATH 验证记录](portability-followup-20260928.json)保存完整运行时入口与最终入口的不同哈希，并验证只有这一行差异；最终解析器实际启动 Vivado 批处理 Tcl、核对 2025.1 并正常退出。最终入口未重复执行五阶段，不能把前一份摘要的入口哈希当作最终版本哈希。原生 `-version` 在本机正常打印版本却返回 1，因此后续核验采用明确的 Tcl 完成标记与退出码。
