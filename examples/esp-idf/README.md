# ESP-IDF / ESP32 原创统计组件示例

本示例演示 Kconfig 配置、当前配置保留、原生 CMake 组件接入与共享 C 模块。目标参考版本是 **ESP-IDF v5.5.4，目标 esp32**。本轮仅完成文档核实与源码适配；**原生配置生成、目标构建、下载和板上运行均为 NOT_RUN**，不提供固件或模拟的编译通过日志。

原创部分采用仓库 [MIT 许可证](../../LICENSE)，Copyright (c) 2026 YuWYY。ESP-IDF、工具链、FreeRTOS、厂商组件与其他传递依赖保持各自许可证并由外部环境提供；本仓库不复制 SDK、厂商模板或依赖代码。

## 配置与实现

| 内容 | 来源 |
|---|---|
| `CONFIG_EPW_STATS_WINDOW` 整数范围 `1..16`、默认 `8` | `main/Kconfig` |
| 新工程目标 `esp32` 和窗口默认 `8` | `sdkconfig.defaults` |
| 用户当前窗口值 | 未来真实配置工具生成或保存的 `sdkconfig`；本源码交付没有该文件 |
| 状态、采样存储、一次性合成批次 | `main/app_main.c` 中的调用者对象 |
| 无平台依赖的统计实现 | [共享模块](../common/rolling-stats/README.md) |
| 共享源码与公共头文件的 IDF 接入 | `components/epw_stats/CMakeLists.txt` |

`app_main` 在 IDF 已有主任务中推入 `10,20,...,90` 九个合成值，读取最新窗口统计后返回。没有额外应用任务、网络、外设采样或持久存储逻辑；SDK 启动和内部服务不因此消失。IDF 允许 `app_main` 返回，见 [v5.5.4 启动流程](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/startup.html#running-the-main-task)。

按输入和算法推导，窗口 `8` 时最终计数 `8`、最小值 `20`、最大值 `90`、均值 `55`；窗口 `16` 时计数 `9`、最小值 `10`、最大值 `90`、均值 `50`。这是未来观察的预期值，并非板上日志。均值为整数除法；组件容量及错误处理契约见共享模块。

存储数组长度与初始化容量均直接使用 `CONFIG_EPW_STATS_WINDOW`。例如用户当前 `sdkconfig` 为 `16`、defaults 为 `8` 时，应保留并使用当前 `16`；defaults 只定义默认选择。变更当前值使用 `menuconfig`，不编辑派生 `sdkconfig.h`。[v5.5.4 工程配置指南](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/kconfig/project-configuration-guide.html)

## 未来真实重建步骤

以下命令**本轮未执行**。前提是已安装并激活 ESP-IDF v5.5.4 的环境及其工具链；此说明不包含下载、安装或升级。使用完整仓库副本，保留 `examples/esp-idf/` 与 `examples/common/rolling-stats/` 的相对位置。仅复制本示例目录会缺少共享源码。

官方构建文档声明组件路径不能包含空格；未来验证使用无空格的短路径仓库副本。中文路径兼容性未验证。[v5.5.4 构建系统](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/build-system.html)

在已激活的 ESP-IDF PowerShell 中，进入该副本的 `examples/esp-idf`，先执行并核对输出确为 v5.5.4：

```powershell
idf.py --version
```

确认后，在本 PowerShell 进程禁用 Component Manager；本示例只用本地组件和 SDK 自带 `log` 组件，无需下载受管理依赖：

```powershell
$env:IDF_COMPONENT_MANAGER = '0'
idf.py -B build -DIDF_TARGET=esp32 reconfigure
idf.py -B build build
```

以上命令从源码目录读取 defaults，真实生成 `sdkconfig` 和 `build/` 下的配置与构建产物。若是已有工程，先核对当前目标与配置；目标冲突时停止该命令流程并处理差异。不要顺手运行 `set-target`：它会清理构建目录并重建当前配置。[v5.5.4 idf.py](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/tools/idf-py.html)；禁用管理器的环境变量见 [v5.5.4 Component Manager](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/tools/idf-component-manager.html#disabling-the-component-manager)。

要检查当前配置改为 `16` 后仍有效，在同一工程执行：

```powershell
idf.py -B build menuconfig
idf.py -B build reconfigure
idf.py -B build build
```

在菜单的 `Component config` → `EPW statistics example` 中把窗口改为 `16`，保存退出；随后核对 `sdkconfig` 的值和真实生成的 `build/config/sdkconfig.h`，defaults 保持 `8`。应同时检查 CMake 实际编译了共享 `epw_stats.c`、入口参与链接以及真实命令退出码。退出当前 PowerShell 或恢复原来的进程环境变量即可结束此临时管理器设置。

本说明没有 flash、monitor、串口、下载或硬件步骤。目标构建成功也不等于应用已经启动；若后续取得板上观察，应单独记录固件身份和真实输出。

## 当前证据

官方文档机制核对日期为 2026-09-30，来源和完整配置边界见 [ESP-IDF 专用指南](../../skills/embedded-project-workflow/references/esp-idf.md)。本目录保留作者维护的配置与源码，不带 `sdkconfig.h`、固件、SDK 桩或原生构建日志。共享模块主机测试与 ESP-IDF 原生验证分开记录，前者不能替代后者。
