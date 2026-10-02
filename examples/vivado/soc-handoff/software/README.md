# A53 应用与 Vitis 交接步骤

本目录是原创应用源码与后续操作说明。v0.5 本机未找到配套 A53 编译器，平台创建、BSP 生成/编译、应用编译/链接、ELF、下载及运行均为 **NOT_RUN**。这里没有模拟 BSP 或生成头文件。硬件/SDT 的结果不能替代这些阶段。

## 当前接口

一个 dual AXI GPIO：通道 1 两位输出，bit 0 使能、bit 1 清零；通道 2 为 32 位计数输入。清零优先于使能，停用使能保持计数。默认停止；32 位溢出回绕。硬件地址只能从当前原生硬件与平台派生，应用不固化 A/B 地址。

`app_main.c` 使用 SDT 流程的 `XGpio_Initialize(instance, BaseAddress)`。本机 2025.1 的 `gpio_v4_12/src/xgpio_sinit.c` 与官方 GPIO 示例支持此接口及 canonical `XPAR_XGPIO_0_BASEADDR`。真正生成 BSP 后仍须核对该宏对应本案例 `axi_gpio_0`，不能因为名字存在就认定映射正确；若不匹配，调整用户层绑定，不能手改生成头文件或补造 DEVICE_ID。

代码只演示配置、使能、观测和暂停，没有板级通过判断。后续运行前还须核对 MMIO 属性、初始化、真实时钟与复位、读写顺序。返回 XST_SUCCESS 只代表这段程序未遇到初始化错误，不是计数功能验收。

## 具备匹配环境后的原生步骤（本轮未执行）

使用 Vitis Unified 2025.1 与匹配的 A53 工具链。先通过 doctor 核查组件，不能拿另一套 STM32 GCC 或 HLS 安装目录代替 A53 环境。不要为本轮说明自动安装软件。

1. 从当前 Vivado 工程导出已核对的 XSA，保留它与 BD、源码及本轮报告的对应关系。
2. 在一个新 workspace 创建 standalone 平台，目标 `psu_cortexa53_0`、64-bit，domain 名为 `standalone_a53`。本例不打包启动镜像，关闭不需要的 boot components；此设置不能用于推断板卡无需启动固件。
3. 生成并构建真实平台/BSP；核对 SDT、`xparameters.h`、GPIO 配置表、驱动版本、处理器和可达内存。只有此步完成后才能核对实际宏和应用绑定。
4. 以平台实际导出的 XPFM 创建 empty application，将本目录 `app_main.c` 导入其用户 `src`，确保没有另一个 `main`。通过原生链接脚本编辑器选择真实内存；检查代码/数据/栈/堆与最终 ELF/MAP。不要把这一步写成已有通过结果。
5. BD 改变后，使用平台的 **Switch / Re-Read XSA** 或当前 API `platform.update_hw(hw_design=...)` 更新，再构建平台和应用。确认软件地址也随硬件变化，而非只看工程 Build PASS。

以下片段按本机 2025.1 API 源码核对，但 **没有原生执行**。路径变量指向操作者自己的隔离 workspace/实际产物，不是自动下载、安装或硬件调试入口：

```python
import vitis
client = vitis.create_client()
client.set_workspace(workspace_path)
platform = client.create_platform_component(
    name="epw_platform", hw_design=xsa_path,
    os="standalone", cpu="psu_cortexa53_0",
    domain_name="standalone_a53", architecture="64-bit",
    compiler="gcc", no_boot_bsp=True, generate_dtb=False)
platform.build()
# exported_xpfm comes from this platform's actual output, never a guessed old file.
app = client.create_app_component(
    name="epw_counter", platform=exported_xpfm,
    domain="standalone_a53", template="empty_application")
app.import_files(from_loc=application_source_dir,
                 files=["app_main.c"], dest_dir_in_cmp="src")
app.build()
# Later, on this same platform instance:
platform.update_hw(hw_design=updated_xsa_path)
platform.build()
app.build()
```

`template` 必须以当前安装实际列出的 empty application ID 为准；上述名称需在可运行的 Vitis 环境中确认。使用本机 CLI/API 文档查看实际返回状态，分别记录平台生成、BSP 编译及应用编译，失败不能进入成功阶段。交互式 Python 片段不是本轮已验证的通用构建器。

官方依据：[硬件更新](https://docs.amd.com/r/2025.1-English/ug1400-vitis-embedded/Updating-the-Hardware-Specification)、[Python API](https://docs.amd.com/r/2025.1-English/ug1400-vitis-embedded/Python-API-A-Command-line-Tool-for-Creating-and-Managing-Projects-in-Vitis)、[SDT 驱动迁移](https://docs.amd.com/r/2025.1-English/Vitis-Tutorials-Embedded-Software/Vitis-YAML-file)。仅依接口自行编写应用，没有复制厂商库；真正的 BSP/驱动由用户本机合法安装提供。
