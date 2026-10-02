# 原创滚动统计核

本模块服务本轮原创案例，采用 MIT，署名 YuWYY。它不依赖 RTOS、GUI 或厂商 SDK，不为 Skill 规定通用任务数量、窗口大小或采样周期。

调用者提供状态、`uint32_t` 存储及 1～16 的容量。`epw_stats_init` 初始化，`epw_stats_push` 加入样本，`epw_stats_reset` 清空窗口，`epw_stats_read` 输出 `count/minimum/maximum/mean`。读取空窗口返回 false 并清零结果；有效均值按当前样本数向下取整，满窗口后覆盖最旧样本，累加使用 `uint64_t`。不分配堆内存；并发访问的同步由宿主负责。

在仓库根执行主机契约测试，明确提供已有 C 编译器及仓库外的新输出目录：

```text
python -B examples/common/rolling-stats/tests/check.py --cc <已有GCC可执行程序> --output <新的主机测试目录>
```

测试运行真实 C 源码，预期结果独立于实现；另在输出目录编译一个故意返回错误均值的包装，要求契约测试因均值错误而退出失败。负例不修改生产源码。

这些结果仅证明主机业务行为。CubeMX 的生成/目标链接、TouchGFX 的用户接入/Simulator交互以及 ESP-IDF 的目标构建各自验证，不能由此替代。
