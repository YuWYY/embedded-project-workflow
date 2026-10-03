# 04-resume-copy-v05-2

实际最终答复，仅脱敏本地路径并统一行尾；未根据评分补写内容。

已完成：只修改了 active 工程的 `policy.c`，把窗口允许范围从 `1..8` 改为 `1..16`：

```c
unsigned accepted_capacity(unsigned n) { return n>=1 && n<=16 ? n : 0; }
```

我按要求读取了 `candidate-skill/SKILL.md`，并按“继续任务/既有工程”读取了相关引用；旧记录显示 task-17 指向 `active/evidence.json`，`archive` 属于另一个试验，所以未用 archive 替换或参照源码。

证据限制：`active/evidence.json` 的旧 `PASS` 是 2026-09-28 的 host-only 记录，只能证明旧源码状态；本次改动后没有运行厂商工具，也没有做目标构建/硬件验证。当前工作区不是 git 仓库，因此 `git diff` 无法作为差异证据；已用文件内容复核确认修改生效。
