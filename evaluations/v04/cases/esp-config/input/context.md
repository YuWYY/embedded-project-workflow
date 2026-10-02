# 原始场景材料

这里是原创合成评估输入，不是真实 IDF 工具输出。`sdkconfig` 只是表达用户已保存值的最小测试夹具，不是完整、可独立构建的厂商生成配置。

在隔离工作目录中取仓库 `examples/esp-idf/` 及 `examples/common/rolling-stats/` 为源码基线，保持二者相对位置；用这里的 `main/app_main.c`、`sdkconfig` 和 `sdkconfig.defaults` 覆盖对应示例文件。其他原生 CMake、Kconfig 和共享模块保持基线版本。只修改隔离副本，不改仓库评估原件。

工程契约：使用 IDF 已有主任务的 app_main，不创建额外应用任务；`app_heartbeat` 的已有一次递增保留。最新窗口选择以本输入表达的 16 为准。没有真实 SDK、编译头文件、原生构建结果或板上证据可供本案例复用。
