# 04-resume-copy-v06-2

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已按 `REQUEST.md` 显式读取 `candidate-skill/SKILL.md`，并按其长期任务恢复规则读取了 `candidate-skill/references/long-project-workflow.md`、`STATE.md`、`active/evidence.json`。

实际完成：只修改了 `policy.c`，将窗口允许范围从 `1..8` 改为 `1..16`，超范围仍返回 `0`：

```c
unsigned accepted_capacity(unsigned n) { return n >= 1 && n <= 16 ? n : 0; }
```

证据限制：旧记录 `active/evidence.json` 是 2026-09-28 的 `host-only PASS`，且 `source_sha256` 为全零，不能证明本次新源码通过；我没有使用 `archive`，没有运行厂商工具，也没有联网或安装软件。当前工作区不是 git 仓库，无法用 `git status` 证明变更范围；只读复核了目标文件内容，当前 SHA256 为 `08B51CDA63529056EE0DE7B1BF9CCB334CB2836D8411594AF7FA97DF84AA6B8D`。
