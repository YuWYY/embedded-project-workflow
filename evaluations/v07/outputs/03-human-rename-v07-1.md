# 03-human-rename-v07-1

> 原始最终答复，仅将本地绝对路径脱敏为工程相对路径或工具代号；未补入后续独立验证结果，也未修正原答复判断。

已完成用户层接续，未改 Designer 页面文件、未添加 `clearAndResume`、未生成/构建。

实际修改：
- `gui/StatisticsView.hpp`：把旧声明 `resetStatistics()` 改为 `clearWindow() override`
- `gui/StatisticsView.cpp`：实现 `StatisticsView::clearWindow()`，仍调用 `model.clearStats()`

证据范围：
- `Statistics.touchgfx` 当前回调为 `clearWindow`
- `interface/StatisticsViewBase.hpp` 当前接口为 `virtual void clearWindow()`
- `gui/Model.hpp` 中 `clearStats()` 只执行 `samples=0`，不修改 `paused` 和 `count`，符合“清空只清统计，不动暂停和原计数”
- 全文静态搜索未再发现 `resetStatistics` 或 `clearAndResume`

限制说明：本工作区不是 git 仓库；按请求没有调用 SDK、没有执行 TouchGFX 生成、没有构建或目标验证。
