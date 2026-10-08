# 维护、校验与发行

本页说明 **v0.8.0-beta.2 公开预览版**的维护与发布流程。发布目标固定为 `YuWYY/embedded-project-workflow` 的 `v0.8.0-beta.2`；实际发布提交、附件和状态以[本版 Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.8.0-beta.2)及[对应提交的 CI](https://github.com/YuWYY/embedded-project-workflow/actions/workflows/validate.yml)为准。发布准备时远端 CI 尚未运行，流程描述及本地通过都不表示远端步骤已经完成。能力与证据范围见[支持表](support.md)，下载与解压不会安装或启用 Skill。

打包命令使用脚本中的当前版本 `0.8.0-beta.2`。五份可编辑 SVG 模板及绘图源码随 Skill 包交付；PNG 为本地生成预览，不进入文本源码白名单。SVG 生成使用标准库，PNG 依赖仅影响预览。beta.1、beta.2 本地验证报告及下文 v0.7/v0.5 记录保持各自历史身份，不倒改当时的“未发布、远端 CI 未执行”结论。

所有命令从仓库根目录运行，需要 Python 3.12 标准库。仓库源码与发行物采用明确清单；不从任意目录整体归档，也不自动收集日志。

## 日常修改

1. 修改相关源码或文档，新文件逐项加入 `source-files.txt`。不加入实际工程、原始日志和厂商生成产物。
2. 运行 `python -B scripts/release.py refresh-manifest`。这项**显式维护操作**按现有白名单重算 `release-manifest.json`；它不自动增加白名单文件，也不代表审阅批准。
3. 审阅源码、白名单与清单差异，然后运行：

```powershell
python -B scripts/release.py validate
python -B scripts/release.py self-test
python -B scripts/release.py pack
python -B scripts/release.py verify-packages
```

`validate` 不会修复或更新清单。内容改变却未显式重算清单时，它必须失败。受控负例只写入 `.cache/` 内临时副本，不改真实来源文件。正常编辑无需与旧候选永远字节相同；每个发行版本以审阅后的当前清单为准。

`source-files.txt` 自身纳入哈希清单，`release-manifest.json` 是唯一不自哈希的元文件。校验器拒绝所有不在白名单中的源码文件，仅忽略 `.git/`、`dist/`、`.cache/` 与 Python 字节码缓存。`.gitignore` 不是发布授权白名单。

`.gitattributes` 禁用自动文本换行转换，使 Windows 与远端全新克隆保留清单所校验的原始字节。`self-test` 的源码改动负例还实际启动 CLI，要求因清单不符退出 1。

## 发行物

`pack` 先完整校验，再写入 `dist/`：

- `embedded-project-workflow-source-v<version>.zip`：完整的审阅白名单源码与 `release-manifest.json`，包含 README、Skill、指南、检查脚本、原创示例和评估输入；适合首次试用与复核来源。
- `embedded-project-workflow-v<version>.zip`：仅 Skill 目录中的指南与窄适配脚本，加上归档根内的 MIT LICENSE。
- `vivado-examples-v<version>.zip`：独立 Vivado 原创示例源码，加上 MIT LICENSE。
- `SHA256SUMS.txt`：以上三个 ZIP 的 SHA-256。

三个 ZIP 必须来自同一份通过清单校验的源码、使用同一版本；完整源码 ZIP 不等同于 GitHub 自动生成的 Source code 附件。归档使用固定元数据和排序；相同来源应生成相同字节。`verify-packages` 独立核对归档条目、CRC、每项内容与来源以及附件校验值，拒绝多余条目和被替换的数据。

CubeMX/FreeRTOS、TouchGFX、ESP-IDF与共用业务模块的原创示例及合成评估材料在仓库中交付，不另打入 Skill ZIP。Vivado ZIP 包含原始两个示例、受控配置与续接示例，以及原创 MPSoC 硬件交接案例；软件源码的 NOT_RUN 说明同时保留。厂商依赖始终由本机已有安装提供。

CI 执行 validate、self-test、隔离runner证据/路径回归、合成案例准备、pack、verify-packages，并上传构建附件。runner故障回归模拟厂商子进程，不运行Vivado；Windows进程树测试会创建和清理自身Python父子孙进程，并核对独立同名进程存活。案例准备只复制原创输入与 Skill，不能代替模型执行和行为评分。CI 不自动创建 Release，不运行厂商工具，不安装 Skill，不操作硬件。

## v0.8.0-beta.2 发布流程

1. 从远端当前 `main` 建立独立发布工作区与分支，只同步审阅白名单中的公开文件，统一版本为 `0.8.0-beta.2`。保留本地候选与原始工程，不把隔离实验、私有工程、厂商生成树或原始个人日志带入 Git 历史与附件。
2. 完成本页的清单维护、审阅、本地校验、负例检查、三包构建与 `verify-packages`。核对五份 SVG 模板随 Skill 包交付，三包来自同一份源码，校验值逐字节对应。文档修改后重新生成清单和发行物，不能复用旧包或旧校验值。
3. 提交发布 PR，检查实际提交的全部必要 CI 结果。发生修订后，以新提交重新核对；在远端结果返回前保持未执行或待完成状态，不引用旧版本 CI 代替。
4. 合并后独立回读远端最终来源，重新校验清单、构建并核对三包。若 Git clone 不可用，保留限制，使用逐文件哈希核验的远端 API 导出，不称为全新克隆。
5. 上述核对完成后，将 `v0.8.0-beta.2` 标签指向已核对的最终提交，创建 GitHub prerelease，上传三个 ZIP 与 `SHA256SUMS.txt`。回读实际 Release、标签、附件及 SHA-256，确认其来源与最终提交一致。

固定下载入口：[完整源码 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.8.0-beta.2/embedded-project-workflow-source-v0.8.0-beta.2.zip)、[Skill ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.8.0-beta.2/embedded-project-workflow-v0.8.0-beta.2.zip)、[Vivado 示例 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.8.0-beta.2/vivado-examples-v0.8.0-beta.2.zip)及 [SHA256SUMS.txt](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.8.0-beta.2/SHA256SUMS.txt)。这些链接使用本次固定 tag，实际可用状态以 Release 记录为准。

发布说明分别陈述图稿、独立交付、原生工具及硬件证据：本轮 11 次首次交付复核通过，允许交付前自修；其中 9 对图及 2 次不扩展绘图的任务。STM32 100→200 ms 有当前源码契约、Debug/ELF/MAP 证据；FPGA 125→100 MHz 有生成、XSim、OOC 与顶层综合证据。保留[beta.2 原始记录](validation-v08b2.md)中的局部 T 形漏报、私有契约适用范围、外层 runner 异常及所有未覆盖项，不把原生阶段完成写成全部进程成功，不把这些结果写成板级验证或统计提效。未修改的历史厂商流程不机械重跑，也不改称本轮已执行。

## v0.7.0-beta.1 发布流程（历史）

1. 在独立发布仓库中，只同步审阅白名单内的公开文件；版本统一为 `0.7.0-beta.1`。原始工程、厂商内容、隔离实验目录和个人日志不上传。
2. 更新并审阅清单，完成本地校验、负例检查、三包构建和 `verify-packages`。检查三包内容边界、同一来源及校验值；本地结果不替代远端 CI。
3. 提交发布 PR，查看该提交的全部必要检查；发生修订后以新提交重新核对。实际 PR、CI 和最终 commit 由发布说明记录，不提前写为通过。
4. 合并后独立回读远端最终来源，重新校验清单、构建并核对三个包。若 Git clone 不可用，明确记录限制，使用逐文件哈希核验的远端 API 导出；不把它称为全新克隆。
5. 仅在上述核对完成后，将 `v0.7.0-beta.1` 标签指向已核对的最终提交，创建 GitHub prerelease，上传三个 ZIP 与 `SHA256SUMS.txt`，然后核对实际附件及校验值。

v0.7 的历史入口为 [Release](https://github.com/YuWYY/embedded-project-workflow/releases/tag/v0.7.0-beta.1)、[完整源码 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/embedded-project-workflow-source-v0.7.0-beta.1.zip)、[Skill ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/embedded-project-workflow-v0.7.0-beta.1.zip)、[Vivado 示例 ZIP](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/vivado-examples-v0.7.0-beta.1.zip)和[校验值](https://github.com/YuWYY/embedded-project-workflow/releases/download/v0.7.0-beta.1/SHA256SUMS.txt)。这些入口保留 v0.7 身份；新版试用使用上方 beta.2 入口。

发布说明应区分本地回归、代理行为与定向复验、真实厂商工具生成/构建、独立接入检查和真人试用。沿用记录中尚未执行的板测、Vitis A53 原生软件构建等边界；不把首次失败后的定向复验合并成首次全通过。历史 `validation` 文档保持原始结论，由实际 Release/PR/CI 记录补充公开发布阶段的事实。

## v0.5 公开预览版发布记录（历史）

v0.5 候选完成后另行获得公开发布授权。发布分支从远端当前 main 建立，仅同步白名单中的审阅文件；不上传本地隔离历史。PR 的 CI 通过后合并，独立取得远端来源并重新验证清单、构建和核对包，再创建 `v0.5.0-beta.1` 标签及 GitHub prerelease，上传 `dist/` 中两个 ZIP 和校验文件。若网络使 Git clone 无法执行，应保留这一限制并通过逐文件哈希核验的远端 API 导出完成来源回读，不称为全新克隆。

后续发布说明分别列出历史行为、本轮定向行为复验、实际 Vivado/SDT/RTL 仿真、真人维护证据，以及 A53 平台/BSP/应用构建缺口。历史 CubeMX/TouchGFX 工具结果及 ESP-IDF 资料与源码保留其原有身份。未通过本轮验收不能发布为已通过。版本完整执行后若还有小范围修订，保留两个源码身份，说明定向复验和未重复的流程。若某项未覆盖，应直接标明，不能以缓存日志或模拟输出代替。原始私有材料保持本地，不随 Git 历史或附件发布。

候选期间的“未推送、未发布”和“远端 CI 未运行”描述属于当时的验证状态，保留在历史报告；公开发布状态以 GitHub 的 PR、Actions 和 Release 记录为准。此次公开预览汇集可靠执行与窄 CubeMX 适配、既有工程功能接手及 TouchGFX 真人交互接续、板级依据和 MPSoC 元数据交接。A53 软件原生构建与板测仍未执行。

发布前首轮 Windows CI 暴露了 SoC 重建测试夹具的路径拼写不一致：`project_inputs` 返回规范路径，夹具却直接沿用 `TEMP` 提供的路径。夹具现在使用与实际 CLI 相同的 `unlinked` 路径检查和规范化，再构造期望路径。没有修改生产入口、放宽额外 HDL 或链接路径拒绝规则，也没有把这次主机测试修订记为重新执行厂商综合。38 项普通模式及 38 项优化模式在本地复验通过；远端整套结果以 PR #2 的当前提交检查为准。
