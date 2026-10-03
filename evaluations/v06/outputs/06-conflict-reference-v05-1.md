# 06-conflict-reference-v05-1

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已完成：把 `prj.conf` 的采样周期从 `10` 改为 `20`：

```conf
CONFIG_APP_SAMPLE_PERIOD_MS=20
```

判断结果：第三方摘述里“统计应独占新任务”与 `PROJECT.md` 的“最多两个任务（采样、界面）”冲突，不能采用。最小方案是：统计在现有采样任务内累计/更新，界面任务只读取并显示统计结果；必要时用已有同步机制保护共享统计数据，不新增第三任务。

证据限制：我只读取了当前工作区内的 `REQUEST.md`、`candidate-skill/SKILL.md`、相关 `freertos.md`、项目文件和本地 references；未访问网络、未查看父级/旁路目录。当前无 SDK/编译器，所以只做了文本级核对：`20` 在 `Kconfig` 的 `range 1 1000` 内，且 `.conf` 使用 `CONFIG_<symbol>=<value>` 与工作区官方摘述一致。这里不是 git 仓库，因此没有可用的 `git diff` 证据。
