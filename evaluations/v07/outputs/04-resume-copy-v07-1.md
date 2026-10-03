# 04-resume-copy-v07-1

> 原始最终答复，仅将本地绝对路径脱敏为工程相对路径或工具代号；未补入后续独立验证结果，也未修正原答复判断。

已完成请求：显式读取了 `candidate-skill/SKILL.md`，并按其续接场景读取了 `candidate-skill/references/long-project-workflow.md`。只修改了 `active/APP/policy.c`，将窗口允许范围从 `1..8` 改为 `1..16`，超范围仍返回 `0`：

```c
unsigned accepted_capacity(unsigned n) { return n>=1 && n<=16 ? n : 0; }
```

证据范围：我只做了源码级核对，确认目标文件当前内容正确；未运行厂商工具、未生成、未构建、未访问网络，也没有使用 `archive`。旧记录 `active/evidence.json` 是 task-17 的 host-only PASS，但 `source_sha256` 为全零占位，且本轮源码已改变，因此不能作为本次修改后的通过证据。当前目录也不是 git 仓库，无法用 `git diff` 留存仓库级差异。
