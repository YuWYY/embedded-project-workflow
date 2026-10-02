# 原创分析材料

本材料只描述工程，不是已运行工具记录。
STM32G474RE；CubeMX 6.18.1；CMSIS-RTOS2；ARMCC5。
IOC维护 SampleFeed/StatsWorker 两个任务及静态 uint32_t 队列 SampleQueue。
SampleFeed 负责合成输入，StatsWorker 负责消费。两者实现位于 Services 与 Domain 目录。
任务及队列由 Core/Src/app_freertos.c 创建；独立用户入口由 Keil 项目引用。
目标是窗口8的样本统计，纯C实现，使用现有队列。不增加任务。
