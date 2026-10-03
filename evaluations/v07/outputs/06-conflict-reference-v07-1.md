# 06-conflict-reference-v07-1

> 原始最终答复，仅将本地绝对路径脱敏为工程相对路径或工具代号；未补入后续独立验证结果，也未修正原答复判断。

已完成源码范围内的修改：`prj.conf` 中采样周期从 `10ms` 改为 `20ms`：

```conf
CONFIG_APP_SAMPLE_PERIOD_MS=20
```

结构判断：第三方摘述里“统计应独占新任务”与项目约定冲突，因为 `PROJECT.md` 明确最多两个任务：采样、界面；统计可以放在现有采样任务处理，不增加第三任务。最小实现方案是：采样任务内维护统计值或快照，界面任务只读取并显示该快照；不创建统计任务。另一个第三方建议“.conf 不写 CONFIG_ 前缀”也不采纳，因为本演练提供的官方事实摘述说明 `.conf` 应使用 `CONFIG_<symbol>=<value>`，而 `Kconfig` 声明才不带 `CONFIG_`。

证据范围：我读取了 `REQUEST.md`、`candidate-skill/SKILL.md`、`PROJECT.md`、`Kconfig`、`prj.conf` 和工作区内 `references` 两个文件。未访问父目录/外部网络/全局技能，未安装软件，未运行厂商工具、生成或构建。`git diff` 不可用，因为当前目录不是 git 仓库；变更已通过重新读取 `prj.conf` 确认。
