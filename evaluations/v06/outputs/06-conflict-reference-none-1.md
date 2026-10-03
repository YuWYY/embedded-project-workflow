# 06-conflict-reference-none-1

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已完成：

- 已将 `prj.conf` 中采样周期从 `10` 改为 `20`：`CONFIG_APP_SAMPLE_PERIOD_MS=20`。
- 判断统计显示方案：第三方摘述建议“统计独占新任务”与 `PROJECT.md` 的“最多两个任务，统计可在采样任务处理”冲突，因此最小实现方案是不新增统计任务，把统计计算并入现有采样任务，界面任务只读取/展示统计结果。
- `.conf` 中保留 `CONFIG_` 前缀，依据是工作区内 `references/official-facts.md` 的说明；未采用 `external-skill.txt` 中相反建议。

证据限制：我只读取并修改了当前 workspace 内文件；没有访问父级/同级目录、网络、SDK、编译器或外部工具，因此未做实际构建验证。
