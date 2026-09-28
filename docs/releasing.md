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

- `embedded-project-workflow-v0.1.0-beta.1.zip`：Skill 目录中的文件，加上归档根内的 MIT LICENSE。
- `vivado-examples-v0.1.0-beta.1.zip`：Vivado 原创示例源码，加上 MIT LICENSE。
- `SHA256SUMS.txt`：两个 ZIP 的 SHA-256。

归档使用固定元数据和排序；相同来源应生成相同字节。`verify-packages` 独立核对归档条目、CRC、每项内容与来源以及附件校验值，拒绝多余条目和被替换的数据。

CI 执行 validate、self-test、pack、verify-packages，并上传构建附件。它不自动创建 Release，不运行 Vivado，不安装 Skill，不操作硬件。

## GitHub 预发布

发布者在本轮真实试用报告完成、仓库校验及相关工具复验通过后，创建 `v0.1.0-beta.1` 标签和 GitHub prerelease。先从远端全新克隆验证清单及包，再上传 `dist/` 中两个 ZIP 和校验文件。

发布说明分别列出历史行为、真实 Vivado、本轮 CubeMX 与结构检查证据。若某项未覆盖，应直接标明，不能以缓存日志或模拟输出代替。原始私有材料保持本地，不随 Git 历史或附件发布。
