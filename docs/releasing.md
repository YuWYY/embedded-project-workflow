# 维护、校验与发行

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

- `embedded-project-workflow-v0.5.0-beta.1.zip`：Skill 目录中的指南与窄适配脚本，加上归档根内的 MIT LICENSE。
- `vivado-examples-v0.5.0-beta.1.zip`：Vivado 原创示例源码，加上 MIT LICENSE。
- `SHA256SUMS.txt`：两个 ZIP 的 SHA-256。

归档使用固定元数据和排序；相同来源应生成相同字节。`verify-packages` 独立核对归档条目、CRC、每项内容与来源以及附件校验值，拒绝多余条目和被替换的数据。

CubeMX/FreeRTOS、TouchGFX、ESP-IDF与共用业务模块的原创示例及合成评估材料在仓库中交付，不另打入 Skill ZIP。Vivado ZIP 包含原始两个示例、受控配置与续接示例，以及原创 MPSoC 硬件交接案例；软件源码的 NOT_RUN 说明同时保留。厂商依赖始终由本机已有安装提供。

CI 执行 validate、self-test、隔离runner证据/路径回归、合成案例准备、pack、verify-packages，并上传构建附件。runner故障回归模拟厂商子进程，不运行Vivado；Windows进程树测试会创建和清理自身Python父子孙进程，并核对独立同名进程存活。案例准备只复制原创输入与 Skill，不能代替模型执行和行为评分。CI 不自动创建 Release，不运行厂商工具，不安装 Skill，不操作硬件。

## 公开预览版发布流程

v0.5 候选完成后另行获得公开发布授权。发布分支从远端当前 main 建立，仅同步白名单中的审阅文件；不上传本地隔离历史。PR 的 CI 通过后合并，独立取得远端来源并重新验证清单、构建和核对包，再创建 `v0.5.0-beta.1` 标签及 GitHub prerelease，上传 `dist/` 中两个 ZIP 和校验文件。若网络使 Git clone 无法执行，应保留这一限制并通过逐文件哈希核验的远端 API 导出完成来源回读，不称为全新克隆。

后续发布说明分别列出历史行为、本轮定向行为复验、实际 Vivado/SDT/RTL 仿真、真人维护证据，以及 A53 平台/BSP/应用构建缺口。历史 CubeMX/TouchGFX 工具结果及 ESP-IDF 资料与源码保留其原有身份。未通过本轮验收不能发布为已通过。版本完整执行后若还有小范围修订，保留两个源码身份，说明定向复验和未重复的流程。若某项未覆盖，应直接标明，不能以缓存日志或模拟输出代替。原始私有材料保持本地，不随 Git 历史或附件发布。

候选期间的“未推送、未发布”和“远端 CI 未运行”描述属于当时的验证状态，保留在历史报告；公开发布状态以 GitHub 的 PR、Actions 和 Release 记录为准。此次公开预览汇集可靠执行与窄 CubeMX 适配、既有工程功能接手及 TouchGFX 真人交互接续、板级依据和 MPSoC 元数据交接。A53 软件原生构建与板测仍未执行。
