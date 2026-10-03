# 04-resume-copy-v06-1

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已完成：按 `REQUEST.md` 要求显式读取了 `candidate-skill/SKILL.md`，并按其“长期任务/恢复”指引读取了 `candidate-skill/references/long-project-workflow.md`。只修改了 active 工程的 `policy.c`：

```c
unsigned accepted_capacity(unsigned n) { return n>=1 && n<=16 ? n : 0; }
```

证据范围：已只读核对 `STATE.md` 和 `active/evidence.json`。旧记录是 `task-17` 的 host-only PASS，但 `source_sha256` 为全 0，且本次源码已从 1..8 改为 1..16，所以旧 PASS 不能证明新源码通过。未运行厂商工具、未访问网络、未替换或使用 archive；工作区不是 git 仓库，因此 `git diff` 无法提供版本差异。
