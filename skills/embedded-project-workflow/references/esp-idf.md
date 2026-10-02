# ESP-IDF 配置与组件接入

用于 ESP-IDF 工程的配置分工、原生组件接入和当前配置保留。先读实际工程，再应用本页；已有原生源文件、用户最新修改和工程约定优先于示例。当前适配依据 **ESP-IDF v5.5.4 / ESP32** 官方文档，交付范围是文档与源码，尚未执行 IDF 配置生成、目标构建或板上运行。

## 识别当前工程

核对实际 IDF 版本、目标芯片、顶层和组件 `CMakeLists.txt`、`Kconfig*`、当前 `sdkconfig`、默认配置、组件清单及已有构建记录。检查是否指定 `SDKCONFIG`、`SDKCONFIG_DEFAULTS` 或额外组件路径；不要假定默认文件名就是实际输入。SDK 不在本机时仍可完成源代码工作，明确原生验证未运行，不自动下载或安装。

| 内容 | 负责位置 | 本轮应如何处理 |
|---|---|---|
| 选项名称、类型、依赖、范围及默认值 | 组件内 `Kconfig` / `Kconfig.projbuild` | 让可维护的应用选择成为正式配置项；Kconfig 定义选项，不实现任务或算法 |
| 用户当前已保存的选择 | 工程实际使用的 `sdkconfig` | 读取并保留最新值；实际变更通过 `idf.py menuconfig` 或对应 IDE 配置器完成 |
| 新配置的可复现默认值 | `sdkconfig.defaults` 及实际指定的 defaults 文件 | 用于新建或尚未设值的选项；不能把 defaults 当成当前配置的强制覆盖 |
| 源文件、包含路径、组件依赖 | 原生 `CMakeLists.txt` | 显式注册自有组件；核对真实编译接入 |
| 应用行为、算法、对象生命周期 | `main/` 或自有 `components/` | 复用已有任务和接口；需要增加结构时遵循用户约定 |
| 派生配置与构建结果 | `build/config/sdkconfig.h`、`sdkconfig.cmake`、JSON、ELF/BIN 等 | 仅检查；回到配置或源码修复，不把补丁写进派生产物 |

配置文件职责与派生格式见 [v5.5.4 配置结构](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/kconfig/configuration_structure.html)。

## 当前值、默认值和生效时机

针对本轮相关选项，同时核对 Kconfig 定义、defaults、当前 `sdkconfig` 和代码读取位置。例如窗口当前已保存为 `16`、defaults 为 `8`，正常配置流程应保留当前 `16`；不要为了与示例一致改回 `8`。保存值合法且依赖满足时，加载顺序是 Kconfig 默认值、defaults、当前配置。不要通过删除当前配置来强迫默认值生效。官方建议用配置工具修改当前值，以处理选项依赖。[v5.5.4 工程配置指南](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/kconfig/project-configuration-guide.html)

Kconfig 可表达选项与依赖、条件默认值和菜单；自有容量选项可声明整数与合法范围。`int`、`range` 和 `choice` 的该版本用法也可在官方 [v5.5.4 Kconfig 源码](https://raw.githubusercontent.com/espressif/esp-idf/v5.5.4/components/esp_system/Kconfig)中核对。`Kconfig` 通常进入组件配置菜单，`Kconfig.projbuild` 进入顶层菜单，按实际需要选择。它们不会自动创建应用任务、队列或采样逻辑；这些由已有框架或自有代码实现。[v5.5.4 组件配置指南](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/kconfig/component-configuration-guide.html)

编译期 `CONFIG_*` 变化需要真实配置处理和构建；不能视为运行时参数。源码通过 `sdkconfig.h` 使用实际生成的值。输出缺失时报告尚未生成，不手写同名头文件充数。

`idf.py set-target` 会清空构建目录并重新创建 `sdkconfig`，旧配置保存为 `sdkconfig.old`。它不是每次构建的前置步骤。已有正确目标时直接使用当前配置；确需切换目标时先保留当前有效配置和差异，再按授权执行并核对新配置。`idf.py reconfigure`、`menuconfig`、`build` 的成功分别只证明其实际完成的阶段。[v5.5.4 idf.py 命令](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/tools/idf-py.html)

## 用户组件与受管理依赖

优先复用工程既有组件划分。自有模块通过组件 `CMakeLists.txt` 的 `idf_component_register` 注册源文件、包含目录及依赖；公共头文件依赖用 `REQUIRES`，仅实现需要的依赖用 `PRIV_REQUIRES`。跨目录共享源码用相对当前列表文件计算出的绝对路径，避免依赖调用命令的工作目录。先检查原有编译接入，不另建一套隐藏构建体系。[v5.5.4 构建系统](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/build-system.html)

`idf_component.yml` 声明受管理组件依赖；Component Manager 在配置时可能解析并下载依赖。`managed_components/` 和 `dependencies.lock` 是工具维护的内容，不手工打补丁。需要修改依赖时使用原有清单、受支持的本地组件或明确的上游修复方式。源码任务不自动授权下载；不需要受管理依赖的自有组件不必增加清单。[v5.5.4 Component Manager](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/tools/idf-component-manager.html)

ESP-IDF 已在主任务内调用 `app_main`，且允许该函数返回。一次性合成计算可以直接使用此入口；不为演示组件复用而新增任务体系。接入既有应用时保留任务职责、优先级、栈及同步约定，不据此推断任意应用都无需新增任务。[v5.5.4 启动流程](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-guides/startup.html#running-the-main-task)

## 最小源码示例与验证边界

完整源码仓库的 `examples/esp-idf/` 提供原创 Kconfig、defaults、CMake 接入和 `app_main`；共享统计实现位于 `examples/common/rolling-stats/`。独立Skill ZIP不包含这些源码示例，需要使用完整仓库。窗口为 `1..16`、默认 `8`，存储由调用者提供。示例不带 SDK、受管理依赖、生成头文件或固件。

本页官方来源核对日期：2026-09-30。实际交付只能表述为“文档机制已核实、源码适配已提供”。独立主机测试只能证明共享算法；源码引用检查不能证明 Kconfig 已解析、IDF 已配置或目标固件可运行。未来原生验证应使用已安装的 v5.5.4，记录版本、当前配置、真实命令与退出码，再检查生成配置、组件编译及链接结果；板上启动和功能观察另记证据。其他版本、芯片、IDE 插件和任意现有项目不在本次实测支持声明中。
