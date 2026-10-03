# 06-conflict-reference-v06-2

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已完成：把 `prj.conf` 中采样周期从 `CONFIG_APP_SAMPLE_PERIOD_MS=10` 改为 `20`，保留 `CONFIG_` 前缀，符合本练习 `references/official-facts.md` 给出的 Zephyr `.conf` 写法。

冲突判断：第三方摘述里“`.conf` 不写 `CONFIG_` 前缀”和“统计独占新任务”均与当前材料冲突。`PROJECT.md` 明确最多两个任务：采样、界面；统计应放在现有采样任务处理，不能新增第三任务。

最小统计显示方案：采样任务内累计/更新统计数据，通过现有界面任务读取或接收统计快照并显示；不新增任务，不改变 `CONFIG_HEAP_MEM_POOL_SIZE=0`，也不禁用语法检查。

证据限制：当前没有 SDK/编译器，也不是 git 仓库；我只做了文件级核对，未执行构建、Kconfig 解析或板上运行验证。
