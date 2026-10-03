# TouchGFX：配置、生成与用户实现

在新建 TouchGFX 工程、改变显示基础配置、增加界面结构或排查再生成回归时阅读。已有工程只改动态数值、交互或业务逻辑时，复用现有生成基础，不要求重新走建项目流程。

用户预设的页面、控件、资源、导航和Designer支持的交互是设计输入，按[用户设计约定](configuration-contracts.md)维护。先利用已有骨架接入行为；不能为方便编码另建页面体系或后台任务绕过约定。涉及结构变化时说明具体影响，已授权范围内直接推进。

## 先确认用途与当前工程

先读实际 `.ioc`、`.touchgfx`、生成标记、用户类和构建入口，确认工具版本。结合已有资料了解显示/触摸用途、需要更新的数据及节拍、屏幕接口与内存位置。只追问会改变实现的缺口；引脚、型号等已有事实不要重复询问，也不要让用户自行设计全部驱动参数。

需要图形化配置时，按“配置项 → 软件位置 → 建议值 → 原因 → 核对方法”给出必要建议，默认由用户操作。用户明确要求代操作后，使用可用的图形工具或厂商生成命令；已有授权不重复询问。缺少操作能力时说明实际可做的部分，不声称完成配置或生成。

引导人工编辑时给出确切工程和页面，将控件名称、显示文字、交互函数分别说明。用户不熟悉界面时分成短步骤，并说明完成后应看到什么；不要只给一串内部标识符。用户报告保存后，以最新源文件核对实际变化；若所需结构缺失，先核对工程位置和当前操作，保护已保存内容。

## 按生成来源划分可编辑范围

| 内容 | 维护方式 |
|---|---|
| 芯片、时钟、引脚、显示接口、DMA/中断及所需外存基础 | 在 CubeMX 工程源配置中修正，再用工具生成；与 [CubeMX 指南](stm32-cubemx.md) 配合 |
| 页面布局、静态控件、图片/字体/文本资源、Designer 支持的交互声明 | 在 Designer 工程中维护并生成；不手改生成数据库或基类 |
| 动态数值、交互实现、页面呈现与业务数据衔接 | 写入 `gui` 的用户 View、Presenter、Model；复用项目已有数据传递方式 |
| 板级触摸、HAL 扩展、自定义加速器等 | 先确认生成器提供的可编辑类及覆盖方法，再在对应用户扩展中实现 |

Designer 的 `generated/gui_generated` 是可重建的基类层，`gui` 是用户实现层；生成器不支持的界面行为可在用户类扩展。[ST：Code Structure](https://support.touchgfx.com/docs/development/ui-development/software-architecture/code-structure)

CubeMX 的 `target/generated` 会再次生成；`target` 同时含有可编辑派生类，不能把整个目录都当成用户文件。例如先核对本工程的 `TouchGFXHAL`、触摸控制器和自定义接口是否属于保留类，再修改；同名 `OSWrappers` 在不同配置中的归属也可能不同。[ST：Generating Code](https://support.touchgfx.com/docs/development/touchgfx-hal-development/generator-how-to/generating-code)、[Modifying Generated Behavior](https://support.touchgfx.com/docs/development/touchgfx-hal-development/generator-how-to/modifying-generated-behavior)

## 从生成结果进入用户代码

新工程采用“必要硬件基础配置 → CubeMX 生成 → Designer 创建/生成界面骨架和资源 → 用户层实现 → 构建与对应验证”。已有可信工程只走本次变化影响的步骤。

- 真实基础错误应修回配置源；工具不能表达的板级行为使用正式用户扩展，不以修改生成文件作为长期修复。
- 在用户层集中管理更新频率、换算、格式和交互状态。硬件数据进入界面时沿用或建立适合当前工程的同步通道，在 GUI 上下文更新控件；不让采样中断直接修改界面对象。
- 不把“Designer 能配置”变成“每次业务参数变化都必须打开 Designer”。若本次确实需要新页面、控件或资源，先让工具生成相应骨架，再实现用户行为。
- 用户参数或初始化覆盖必须在首次使用前生效。外存、帧缓冲或图像资源尚未就绪时，不能提前启动会访问它们的显示路径。

## 动态文本与离线检查

使用库接口时核对实际头文件或对应版本的接口约定，不因函数同名就套用标准 C 库语义。例如 `Unicode::snprintf` 的格式串可以是 `char*`，但 `%s` 参数需要以零结尾的 `UnicodeChar` 序列，不能直接传普通 `char*`；容量按 Unicode 字符数计算，普通 `snprintf` 版本不支持 `%f`。[ST：Unicode API](https://support.touchgfx.com/docs/api/classes/classtouchgfx_1_1_unicode)

动态显示检查首次进入页面的模型值、后续变化通知、缓冲区寿命与终止符、所需字形和刷新调用。定点数需核查符号、小于一单位的负值及整数边界；只处理本次变化涉及的内容，不为文本修改强制重建界面。

主机替身和独立算术检查须说明与实际库的差异，不能仅复写自己的实现或用标准字符串函数替代 Unicode 接口后宣布真实调用正确。缺库时可以报告源码契约和数值检查，但不要把枚举样本数量当作界面或库行为已验证。

## 再生成后的针对性核对

保存可比较的原始状态，生成后只检查受到影响的链路：用户派生类与入口是否仍在、生成基类接口是否改变、源文件/库/包含目录是否仍参与构建、任务与中断调用是否连接。

人工或外部脚本修改后，先读取最新`.touchgfx`及相关`texts.xml`，核对控件名、文本ID和资源引用。处理旧Designer内存副本与磁盘源的冲突，避免保存/生成覆盖外部修改；不擅自丢弃未保存的用户编辑。重命名导致用户View引用失效时，调整用户层接入，不把源配置改回旧值。[官方多人协作说明](https://support.touchgfx.com/4.26/docs/development/ui-development/working-with-touchgfx/multiple-developers)

若涉及显示或存储配置，同时核对 CubeMX 与 Designer 的尺寸/像素格式，帧缓冲大小、地址和存储区域，以及外存初始化早于首次访问。项目采用 cache、DMA 或链接区段时，检查相关变动；不为纯文本更新扩展成全板内存审计。

区分生成完成、模拟器运行、目标构建与真机显示/触摸结果。模拟器通过不能证明外存或显示中断正确；未执行的验证直接标明。

## 既有Simulator工程入口

随包的 [touchgfx_project.py](../scripts/touchgfx_project.py) 提供 `inspect`、`generate`、`build`，首版只验证 Windows / TouchGFX 4.26.1 / Simulator 2.0.0 原生布局与命令。先核对支持范围，不能将其解释为任意硬件工程导入器。

命令、参数来源和路径要求集中在[最小调用：TouchGFX](execution-entries.md#touchgfx当前simulator生成与构建)，只有Skill包也可使用。

`inspect`只读，不启动工具。`generate`使用当前配置生成；`build`已包含一次真实生成和干净Simulator构建，无需事先重复调用generate。报告目录须与工程、工具目录互不包含，并与工程在同一卷；旧generated/build会移入本轮报告以区分陈旧产物。输入路径与原生构建布局有额外窄限制，具体以帮助和检查结果为准。

入口不创建模板、不回灌Screens、不覆盖用户gui。工具允许新增的派生用户类仍可能由原生生成器创建，已有用户文件必须保留。新增交互时沿生成按钮回调、用户override、Presenter和Model检查实际业务；默认空虚函数能构建，不能仅凭编译宣布交互完成。示例准备与既有工程接手的边界见[既有工程指南](existing-projects.md)。

本指南根据 2026-09-27 可见的 TouchGFX 4.26 文档编写；执行时以实际工程版本和生成标记为准。来源及采用边界见 [sources.md](sources.md)。
