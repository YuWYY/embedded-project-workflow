"""Prepare original source excerpts for blind v0.8 trials; never solve a case.

All paths are relative to this repository or to --output. The first six cases
are newly authored planning inputs. The last two reuse the original v0.7 input
materials and requests byte for byte, plus an origin declaration.
Reviewer oracles live outside this repository and are never exported here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import textwrap


def excerpt(value: str) -> str:
    return textwrap.dedent(value).lstrip("\n").rstrip() + "\n"


ORIGIN = excerpt("""
    # 材料来源
    本目录是独立演练使用的原创合成摘录。IOC、约束、接口和用户源码仅供
    阅读项目事实，不是厂商原生生成树，不是完整可构建工程；没有复制厂商库。
    未运行 CubeMX、Vivado、SDK、编译器、实现工具或硬件。周期与接口来自
    本目录材料，CPU 耗时、板上波形、时序收敛和实际接线没有测量证据。
""")


def case(case_id: str, title: str, request: str, files: dict[str, str], *,
         kind: str, reused_from: str | None = None) -> dict:
    return {"id": case_id, "title": title, "kind": kind,
            "request": request, "files": {**files, "MATERIAL_ORIGIN.md": ORIGIN},
            "native_generated": False, "reused_from": reused_from}


def build_cases() -> list[dict]:
    result = []
    result.append(case("01-baremetal-plan", "裸机采集与显示项目", "帮我把这个采集和显示项目做成完整规划，把引脚分配、主循环、定时中断和 DMA 的执行关系讲清楚并画出来。先根据当前目录材料做规划，不改输入源码，不安装或运行厂商工具，也不操作板子。", {
        "PanelLogger.ioc": excerpt("""
            # Original synthetic IOC excerpt; not native generated.
            File.Version=6
            MxCube.Version=6.18.1
            Mcu.CPN=STM32F103C8T6
            Mcu.UserName=STM32F103C8Tx
            Mcu.Package=LQFP48
            Mcu.IP0=ADC1
            Mcu.IP1=DMA
            Mcu.IP2=SPI1
            Mcu.IP3=TIM2
            Mcu.IP4=SYS
            Mcu.IP5=RCC
            Mcu.IPNb=6
            Mcu.Pin0=PA0
            Mcu.Pin1=PA4
            Mcu.Pin2=PA5
            Mcu.Pin3=PA7
            Mcu.Pin4=PB0
            Mcu.Pin5=PB1
            Mcu.Pin6=PB10
            Mcu.Pin7=PC13-TAMPER-RTC
            Mcu.Pin8=PA13
            Mcu.Pin9=PA14
            Mcu.Pin10=PD0-OSC_IN
            Mcu.Pin11=PD1-OSC_OUT
            Mcu.Pin12=VP_SYS_VS_Systick
            Mcu.PinsNb=13
            PA0.Signal=ADC1_IN0
            PA0.GPIO_Label=SENSOR_IN
            PA4.Signal=GPIO_Output
            PA4.GPIO_Label=OLED_CS
            PA5.Signal=SPI1_SCK
            PA5.GPIO_Label=OLED_SCK
            PA7.Signal=SPI1_MOSI
            PA7.GPIO_Label=OLED_MOSI
            PB0.Signal=GPIO_Output
            PB0.GPIO_Label=OLED_RES
            PB1.Signal=GPIO_Output
            PB1.GPIO_Label=OLED_DC
            PB10.Signal=GPIO_Input
            PB10.GPIO_Label=PAGE_KEY
            PC13-TAMPER-RTC.Signal=GPIO_Output
            PC13-TAMPER-RTC.GPIO_Label=RUN_LED
            PA13.Signal=SYS_JTMS-SWDIO
            PA14.Signal=SYS_JTCK-SWCLK
            PD0-OSC_IN.Signal=RCC_OSC_IN
            PD1-OSC_OUT.Signal=RCC_OSC_OUT
            ADC1.DMAChannel=DMA1_Channel1
            ADC1.DMAMode=Normal
            SPI1.Direction=SPI_DIRECTION_1LINE
            SPI1.DMAChannel=DMA1_Channel3
            SPI1.DMAMode=Normal
            RCC.SYSCLKFreq_VALUE=72000000
            TIM2.Prescaler=71
            TIM2.Period=1999
            ProjectManager.ProjectName=PanelLogger
            ProjectManager.ProjectFileName=PanelLogger.ioc
        """),
        "APP/profile.h": excerpt("""
            /* Original schedule constants; excerpts only. HAL ticks are ms. */
            #define KEY_SCAN_MS 10U
            #define DISPLAY_RELEASE_MS 40U
            #define STATUS_RELEASE_MS 100U
            #define ACQUISITION_TRIGGER_US 2000U
            #define ADC_FRAME_ITEMS 8U
        """),
        "Core/Src/main.c": excerpt("""
            /* Original pseudocode-shaped source excerpt, not a generated HAL tree. */
            #include "../../APP/profile.h"
            int main(void) {
                hardware_init();
                start_tim2_interrupt();
                unsigned key_due = HAL_GetTick();
                unsigned display_due = key_due;
                unsigned status_due = key_due;
                for (;;) {
                    unsigned now = HAL_GetTick();
                    if (now - key_due >= KEY_SCAN_MS) {
                        key_due = now; page_key_poll();
                    }
                    if (sample_frame_ready) {
                        sample_frame_ready = 0; fold_adc_frame_into_snapshot();
                    }
                    if (now - display_due >= DISPLAY_RELEASE_MS && !oled_dma_busy) {
                        display_due = now; compose_oled_frame(); oled_start_spi_dma();
                    }
                    if (now - status_due >= STATUS_RELEASE_MS) {
                        status_due = now; update_run_led();
                    }
                }
            }
        """),
        "Core/Src/interrupt_excerpt.c": excerpt("""
            /* Original callback/IRQ ownership excerpt, not vendor code. */
            void TIM2_IRQHandler(void) { tim2_dispatch_irq(); }
            void on_tim2_period_elapsed(void) { acquisition_start_adc_dma(ADC_FRAME_ITEMS); }
            void DMA1_Channel1_IRQHandler(void) { adc_dma_dispatch_irq(); }
            void on_adc_dma_complete(void) { sample_frame_ready = 1; }
            void DMA1_Channel3_IRQHandler(void) { oled_dma_dispatch_irq(); }
            void on_oled_spi_dma_complete(void) { oled_dma_busy = 0; }
        """),
        "PROJECT.md": excerpt("""
            当前项目采用裸机循环，没有 RTOS。ADC 帧缓冲为 8 项，定时器每 2 ms
            请求一次采集；若采集仍忙，acquisition_start_adc_dma 记录跳过次数。
            SPI1 DMA 刷新 OLED，由完成回调解除 busy。main 消费采集完成标记。
            源码是原创行为摘录，函数体未全部提供；没有实测耗时或稳定性日志。
            原理图和封装脚号未交付，材料中的 PA/PB 名是逻辑端口名。
        """),
    }, kind="mcu-baremetal-planning"))

    result.append(case("02-rtos-plan", "周期任务与事件任务", "请为当前采集、串口状态上报和告警工程做完整项目规划，画出引脚与任务执行关系，解释任务怎样等待和传递数据。我需要知道能从配置确定什么、还缺什么。先保留输入，只做规划；没有厂商环境，不生成、构建或上板。", {
        "AlertSampler.ioc": excerpt("""
            # Original synthetic IOC excerpt; not native generated.
            File.Version=6
            Mcu.CPN=STM32G474RET6
            Mcu.UserName=STM32G474RETx
            Mcu.Package=LQFP64
            Mcu.IP0=FREERTOS
            Mcu.IP1=ADC1
            Mcu.IP2=USART2
            Mcu.IP3=SYS
            Mcu.IPNb=4
            Mcu.Pin0=PA0
            Mcu.Pin1=PA2
            Mcu.Pin2=PA3
            Mcu.Pin3=PB10
            Mcu.Pin4=PC13
            Mcu.Pin5=PA13
            Mcu.Pin6=PA14
            Mcu.Pin7=VP_FREERTOS_VS_CMSIS_V2
            Mcu.PinsNb=8
            PA0.Signal=ADC1_IN1
            PA0.GPIO_Label=ANALOG_IN
            PA2.Signal=USART2_TX
            PA2.GPIO_Label=STATUS_TX
            PA3.Signal=USART2_RX
            PA3.GPIO_Label=COMMAND_RX
            PB10.Signal=GPXTI10
            PB10.GPIO_Label=ALARM_IN
            PC13.Signal=GPIO_Output
            PC13.GPIO_Label=ALARM_LED
            PA13.Signal=SYS_JTMS-SWDIO
            PA14.Signal=SYS_JTCK-SWCLK
            FREERTOS.Tasks01=SampleFeed,24,256,SampleFeed_Entry,As external,NULL,Static,SampleFeedStack,SampleFeedTCB;StatusTx,16,384,StatusTx_Entry,As external,NULL,Dynamic,NULL,NULL;AlarmEvent,32,256,AlarmEvent_Entry,As external,NULL,Static,AlarmStack,AlarmTCB
            FREERTOS.Queues01=Samples,16,uint32_t,0,Static,SamplesStore,SamplesTCB
            ProjectManager.ProjectName=AlertSampler
            ProjectManager.ProjectFileName=AlertSampler.ioc
        """),
        "Core/Inc/FreeRTOSConfig.h": excerpt("""
            /* Original configuration facts, not vendor header. */
            #define configUSE_PREEMPTION 1
            #define configTICK_RATE_HZ 500U
            #define configSUPPORT_STATIC_ALLOCATION 1
            #define configSUPPORT_DYNAMIC_ALLOCATION 1
            #define configTOTAL_HEAP_SIZE 6144U
        """),
        "APP/tasks.c": excerpt("""
            /* Original CMSIS-RTOS2 usage excerpt. SDK declarations omitted. */
            #define SAMPLE_PERIOD_TICKS 5U
            #define STATUS_PERIOD_TICKS 25U
            #define ALARM_FLAG 0x1U
            void SampleFeed_Entry(void *argument) {
                unsigned next = osKernelGetTickCount();
                for (;;) {
                    next += SAMPLE_PERIOD_TICKS;
                    osDelayUntil(next);
                    unsigned value = read_latest_adc_value();
                    if (osMessageQueuePut(SamplesHandle, &value, 0U, 0U) != osOK)
                        increment_sample_drop_counter();
                }
            }
            void StatusTx_Entry(void *argument) {
                unsigned next = osKernelGetTickCount();
                for (;;) {
                    next += STATUS_PERIOD_TICKS;
                    osDelayUntil(next);
                    unsigned value;
                    while (osMessageQueueGet(SamplesHandle, &value, 0, 0U) == osOK)
                        fold_value_into_status(value);
                    request_uart_status_dma();
                }
            }
            void AlarmEvent_Entry(void *argument) {
                for (;;) {
                    unsigned flags = osThreadFlagsWait(ALARM_FLAG, osFlagsWaitAny, osWaitForever);
                    if (!(flags & osFlagsError)) set_alarm_led();
                }
            }
            void on_alarm_exti(void) { osThreadFlagsSet(AlarmEventHandle, ALARM_FLAG); }
        """),
        "INTERFACES.md": excerpt("""
            CMSIS-RTOS2 priority 数值在本材料中为 AboveNormal=32、Normal=24、
            BelowNormal=16。AlarmEvent 高于 SampleFeed，高于 StatusTx。
            Samples 的队列项是 uint32_t，容量 16，零超时发送满时累计丢弃。
            告警由 PB10 EXTI 置线程标志，不是固定周期任务。连续相同标志可能合并。
            UART DMA 忙时只保留最新待发送状态。任务 CPU 执行时间和告警到达间隔
            均未测量；材料未给告警最小间隔、Deadline 或可调度性证明。
            数字周期使用 RTOS ticks；HAL 毫秒时基与 RTOS tick 不等同。
        """),
    }, kind="mcu-rtos-planning"))

    result.append(case("03-fpga-single-domain", "单域 FPGA 计数遥测", "用当前顶层接口和约束，为开关控制计数、LED 指示和串口遥测做完整 FPGA 项目规划，把引脚和模块的执行关系画清楚。快照需求是 35 ms。只读这些原材料，输出规划，不运行 Vivado、不下载或操作板卡。", {
        "constraints/telemetry_panel.xdc": excerpt("""
            # Original selected-port constraint excerpt, not a Vivado generated project.
            # Pin facts previously checked against Digilent Basys-3-Master.xdc
            # commit 69d35015d4c3a0cb384a964459593cea5260697a, declaring Rev B.
            set_property -dict {PACKAGE_PIN W5 IOSTANDARD LVCMOS33} [get_ports {sys_clk}]
            set_property -dict {PACKAGE_PIN V17 IOSTANDARD LVCMOS33} [get_ports {gate_sw}]
            set_property -dict {PACKAGE_PIN U18 IOSTANDARD LVCMOS33} [get_ports {clear_btn}]
            set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} [get_ports {led0_out}]
            set_property -dict {PACKAGE_PIN A18 IOSTANDARD LVCMOS33} [get_ports {serial_out}]
            create_clock -name panel_clock -period 10.000 [get_ports {sys_clk}]
        """),
        "rtl/telemetry_panel_top.sv": excerpt("""
            // Original interface/wiring excerpt; implementations omitted.
            module telemetry_panel_top(
                input logic sys_clk, gate_sw, clear_btn,
                output logic led0_out, serial_out);
                localparam int CLOCK_HZ = 100_000_000;
                localparam int SNAPSHOT_CYCLES = 3_500_000;
                logic panel_rst, gate_sync;
                logic [31:0] live_count;
                reset_release_sync rst(.clk(sys_clk), .request(clear_btn), .rst(panel_rst));
                edge_filter sw(.clk(sys_clk), .rst(panel_rst), .raw(gate_sw), .level(gate_sync));
                run_accumulator cnt(.clk(sys_clk), .rst(panel_rst), .enable(gate_sync), .count(live_count));
                blink_decode lamp(.clk(sys_clk), .rst(panel_rst), .count(live_count), .led(led0_out));
                serial_packetizer #(.SNAPSHOT_CYCLES(SNAPSHOT_CYCLES)) packet(
                    .clk(sys_clk), .rst(panel_rst), .count(live_count), .tx(serial_out));
            endmodule
        """),
        "MODULE_CONTRACTS.md": excerpt("""
            目标器件 xc7a35tcpg236-1，板卡资料范围 Basys 3 Rev B；不代表已核对实物。
            五个端口为所选业务接口，不是完整板卡约束。所有模块使用 sys_clk。
            reset_release_sync 异步置复位、在 sys_clk 内同步释放；edge_filter
            使用两级寄存器同步开关。run_accumulator 每拍在 enable 为真时递增。
            blink_decode 与 serial_packetizer 都读取 count，不互相等待。
            serial_packetizer 每 3,500,000 拍捕获一次快照，串口速率 115200，
            每次发送 8 个 8N1 字节，忙时不积压新快照。寄存器读取上一拍的结果。
            这是原创接口契约与连线摘录，无综合、实现、STA、仿真或硬件记录。
        """),
    }, kind="fpga-single-domain-planning"))

    result.append(case("04-fpga-dual-domain", "双时钟域流接口", "我要规划一条 80 MHz 采集域到 100 MHz 打包域的数据通路，中间用异步 FIFO。请根据接口材料给出完整项目规划和图示，说明时钟、复位、写满、读取准备和数据流之间的关系。板卡还没定，只有逻辑接口；不选购、不安装工具、不执行综合或硬件测试。", {
        "constraints/stream_bridge.xdc": excerpt("""
            # Original clock-only constraints; physical placement is not assigned.
            create_clock -name capture_clock -period 12.500 [get_ports {capture_clk}]
            create_clock -name packet_clock -period 10.000 [get_ports {packet_clk}]
            set_clock_groups -asynchronous -group [get_clocks capture_clock] -group [get_clocks packet_clock]
        """),
        "rtl/stream_bridge_interfaces.sv": excerpt("""
            // Original interface declarations only; not implemented or elaborated.
            module stream_bridge_top(
                input logic capture_clk, packet_clk, reset_req,
                input logic [15:0] source_word,
                input logic source_valid,
                output logic source_ready,
                output logic [15:0] packet_word,
                output logic packet_valid,
                input logic packet_ready);
            endmodule
            module async_fifo_16x16(
                input logic wr_clk, wr_rst_n, wr_en,
                input logic [15:0] wr_data,
                output logic full,
                input logic rd_clk, rd_rst_n, rd_en,
                output logic [15:0] rd_data,
                output logic rd_valid, empty);
            endmodule
        """),
        "DOMAIN_CONTRACTS.md": excerpt("""
            capture_clk=80 MHz，周期 12.5 ns；packet_clk=100 MHz，周期 10 ns。
            两者相位和频率关系不保证。目标 FPGA、封装、板卡版本和实体引脚未选定。
            capture_stage 位于采集域，packet_stage 位于打包域，FIFO 深度 16，
            数据宽度 16。write side 的 wr_clk=capture_clk，read side 的
            rd_clk=packet_clk。reset_req 请求公共复位，每个域独立同步释放，
            对应 wr_rst_n 与 rd_rst_n；双方退出复位前不接收或产生有效数据。
            写入条件为 source_valid && source_ready，source_ready=!full；full
            在写域有效。读请求条件为 read_ready && !empty，read_ready 在读域，
            由 packet_stage 的空余位置决定。empty 在读域有效。非 FWFT 契约：
            成功 rd_en 后下一读拍产生 rd_valid 与 rd_data；packet_stage 至少保留
            一项输出位置，packet_ready=0 时保持 packet_valid 与 packet_word。
            FIFO 使用双口存储，Gray 指针跨域同步后生成各域标志；不得把多位数据
            简化成直接两级同步。实现体与 CDC/STA 报告未交付，不能判断布局或收敛。
        """),
    }, kind="fpga-dual-domain-planning"))

    result.append(case("05-revision-conflict", "板卡资料冲突与缺失接口", "帮我为这块面板控制器做完整规划：按键、OLED、串口以及新增的 I2C 温度传感器都需要考虑。我拿到的板卡资料有不同修订，先依据当前工程和附件整理引脚、执行关系与待确认项，不改输入、不替我定板卡版本，不运行工具或上板。", {
        "current/PanelController.ioc": excerpt("""
            # Original synthetic current IOC excerpt; not native generated.
            File.Version=6
            Mcu.CPN=STM32F103C8T6
            Mcu.Package=LQFP48
            Mcu.IP0=SPI1
            Mcu.IP1=USART1
            Mcu.IP2=SYS
            Mcu.IPNb=3
            Mcu.Pin0=PA4
            Mcu.Pin1=PA5
            Mcu.Pin2=PA7
            Mcu.Pin3=PB0
            Mcu.Pin4=PB1
            Mcu.Pin5=PB10
            Mcu.Pin6=PA9
            Mcu.Pin7=PA13
            Mcu.Pin8=PA14
            Mcu.PinsNb=9
            PA4.Signal=GPIO_Output
            PA4.GPIO_Label=OLED_CS
            PA5.Signal=SPI1_SCK
            PA7.Signal=SPI1_MOSI
            PB0.Signal=GPIO_Output
            PB0.GPIO_Label=OLED_RES
            PB1.Signal=GPIO_Output
            PB1.GPIO_Label=OLED_DC
            PB10.Signal=GPIO_Input
            PB10.GPIO_Label=PAGE_KEY
            PA9.Signal=USART1_TX
            PA13.Signal=SYS_JTMS-SWDIO
            PA14.Signal=SYS_JTCK-SWCLK
            ProjectManager.ProjectName=PanelController_R3_draft
            ProjectManager.ProjectFileName=PanelController.ioc
        """),
        "board-notes/rev-A.csv": "signal,mcu_port,note\nOLED_SCK,PA5,SPI1\nOLED_MOSI,PA7,SPI1\nOLED_CS,PA4,GPIO\nSTATUS_TX,PA9,USART1\nPAGE_KEY,PB10,input\n",
        "board-notes/rev-B.csv": "signal,mcu_port,note\nOLED_SCK,PB13,SPI2\nOLED_MOSI,PB15,SPI2\nOLED_CS,PB12,GPIO\nSTATUS_TX,PA2,USART2\nPAGE_KEY,PB10,input\n",
        "BOARD_HANDOFF.md": excerpt("""
            交接标签写 R3，只有包装便签，没有可辨识的 PCB 丝印照片。rev-A.csv 与
            rev-B.csv 都是旧交接摘录，没有谁被确认为 R3 的证据；当前 IOC 尚未据
            实物核线。I2C 温度传感器新增要求需要 SCL、SDA 和报警输入，三个信号
            没有分配；电压、上拉、传感器型号与连接器针号也未交付。
            此处 CSV 是原创冲突资料，不是厂商板卡针脚表或实际连线证明。
        """),
        "APP/schedule.h": excerpt("""
            /* Original bare-metal release intervals; HAL milliseconds. */
            #define KEY_PERIOD_MS 10U
            #define OLED_PERIOD_MS 100U
            #define TEMPERATURE_PERIOD_MS 200U
            #define UART_STATUS_PERIOD_MS 500U
        """),
        "APP/requirements.md": excerpt("""
            裸机主循环定期读按键、合成 OLED 画面、请求温度数据和串口状态。
            新温度报警可影响 OLED 状态栏；告警中断的接口尚未落实。
            业务目标已定，传感器驱动和板卡针脚仍缺材料，没有耗时或中断频率测量。
        """),
    }, kind="mcu-conflicting-board-planning"))

    current_ioc = excerpt("""
        # Original synthetic saved revision r4; not native generated.
        File.Version=6
        Mcu.CPN=STM32F103C8T6
        Mcu.Package=LQFP48
        Mcu.IP0=FREERTOS
        Mcu.IP1=SPI2
        Mcu.IP2=SYS
        Mcu.IPNb=3
        Mcu.Pin0=PB12
        Mcu.Pin1=PB13
        Mcu.Pin2=PB15
        Mcu.Pin3=PB0
        Mcu.Pin4=PB1
        Mcu.Pin5=PB10
        Mcu.Pin6=PA13
        Mcu.Pin7=PA14
        Mcu.Pin8=VP_FREERTOS_VS_CMSIS_V2
        Mcu.PinsNb=9
        PB12.Signal=GPIO_Output
        PB12.GPIO_Label=OLED_CS
        PB13.Signal=SPI2_SCK
        PB15.Signal=SPI2_MOSI
        PB0.Signal=GPIO_Output
        PB0.GPIO_Label=OLED_RES
        PB1.Signal=GPIO_Output
        PB1.GPIO_Label=OLED_DC
        PB10.Signal=GPIO_Input
        PB10.GPIO_Label=PRIMARY_KEY
        PA13.Signal=SYS_JTMS-SWDIO
        PA14.Signal=SYS_JTCK-SWCLK
        FREERTOS.Tasks01=InputPoll,24,256,InputPoll_Entry,As external,NULL,Static,InputStack,InputTCB;ScreenCompose,16,384,ScreenCompose_Entry,As external,NULL,Dynamic,NULL,NULL;FaultEvent,32,256,FaultEvent_Entry,As external,NULL,Static,FaultStack,FaultTCB
        FREERTOS.Queues01=KeyEvents,8,uint32_t,0,Static,KeyStore,KeyTCB
        ProjectManager.ProjectName=OperatorPanel_r4
        ProjectManager.ProjectFileName=OperatorPanel.ioc
    """)
    current_profile = excerpt("""
        /* Original current task configuration facts. */
        #define configTICK_RATE_HZ 1000U
        #define INPUT_PERIOD_TICKS 20U
        #define SCREEN_PERIOD_TICKS 40U
    """)
    result.append(case("06-latest-design", "最新配置与历史副本", "我已经保存了当前版本，请按 current 工程为面板的输入、显示和故障提示做完整规划，把引脚和执行关系画清楚。archive 是之前另一轮工作的历史材料，可用于理解变化。保留当前文件和历史原件，不执行生成、构建或硬件操作。", {
        "current/OperatorPanel.ioc": current_ioc,
        "current/APP/profile.h": current_profile,
        "current/APP/tasks.c": excerpt("""
            /* Original current business excerpt; functions and SDK not complete. */
            void InputPoll_Entry(void *argument) {
                for (;;) { osDelay(INPUT_PERIOD_TICKS); poll_primary_key_into_queue(); }
            }
            void ScreenCompose_Entry(void *argument) {
                for (;;) { osDelay(SCREEN_PERIOD_TICKS); drain_key_events(); refresh_spi2_oled(); }
            }
            void FaultEvent_Entry(void *argument) {
                for (;;) { osThreadFlagsWait(1U, osFlagsWaitAny, osWaitForever); show_fault_marker(); }
            }
        """),
        "current/IDENTITY.json": json.dumps({"task_id": "panel-plan-52", "revision": "r4", "saved": "2026-10-04", "project_file": "OperatorPanel.ioc", "ioc_sha256": hashlib.sha256(current_ioc.encode()).hexdigest(), "profile_sha256": hashlib.sha256(current_profile.encode()).hexdigest()}, ensure_ascii=False, indent=2) + "\n",
        "archive/r2/OperatorPanel.ioc": excerpt("""
            # Original synthetic historical r2 excerpt; not native generated.
            File.Version=6
            Mcu.CPN=STM32F103C8T6
            Mcu.Package=LQFP48
            Mcu.IP0=FREERTOS
            Mcu.IP1=SPI1
            Mcu.IPNb=2
            Mcu.Pin0=PA4
            Mcu.Pin1=PA5
            Mcu.Pin2=PA7
            Mcu.Pin3=PB10
            Mcu.PinsNb=4
            PA4.Signal=GPIO_Output
            PA4.GPIO_Label=OLED_CS
            PA5.Signal=SPI1_SCK
            PA7.Signal=SPI1_MOSI
            PB10.Signal=GPIO_Input
            PB10.GPIO_Label=PAGE_KEY
            FREERTOS.Tasks01=ButtonScan,24,256,ButtonScan_Entry,As external,NULL,Static,InputStack,InputTCB;ScreenCompose,16,384,ScreenCompose_Entry,As external,NULL,Dynamic,NULL,NULL;FaultEvent,32,256,FaultEvent_Entry,As external,NULL,Static,FaultStack,FaultTCB;LegacyTelemetry,8,256,LegacyTelemetry_Entry,As external,NULL,Dynamic,NULL,NULL
            ProjectManager.ProjectName=OperatorPanel_r2
        """),
        "archive/r2/APP/profile.h": "#define configTICK_RATE_HZ 1000U\n#define BUTTON_PERIOD_TICKS 10U\n#define SCREEN_PERIOD_TICKS 50U\n#define LEGACY_TELEMETRY_PERIOD_TICKS 500U\n",
        "archive/r2/IDENTITY.json": '{"task_id":"panel-plan-18","revision":"r2","saved":"2026-10-03"}\n',
        "SCOPE.md": excerpt("""
            当前接手身份是 panel-plan-52 / current / r4；archive/r2 是
            panel-plan-18 的历史副本。本次没有发布、编译或运行记录。
            r4 保存记录：ButtonScan 更名为 InputPoll；LegacyTelemetry 删除；
            原 SPI1 OLED 改用 SPI2；输入周期和画面周期按 current/APP/profile.h。
            当前来源是原创配置与接口摘录，任务耗时及故障事件频度未测量。
        """),
    }, kind="current-revision-planning"))

    old_cases = json.loads((Path(__file__).resolve().parents[1] / "v07" / "cases.json").read_text(encoding="utf-8"))
    for case_id, old_id, title in [("07-small-change", "05-small-change", "小标量修改路由回归"), ("08-first-look", "01-first-look", "首次只读概览路由回归")]:
        old = next(item for item in old_cases if item["id"] == old_id)
        result.append(case(case_id, title, old["request"], dict(old["files"]), kind="routing-regression", reused_from="v07/" + old_id))
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Case path escapes output directory")
    return target


def write_case(item: dict, target: Path) -> dict[str, str]:
    target.mkdir(parents=True, exist_ok=True)
    contents = {**item["files"], "REQUEST.md": item["request"] + "\n"}
    for name, content in contents.items():
        path = safe_target(target, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    hashes = {name: digest(target / name) for name in sorted(contents)}
    (target / "INPUT-HASHES.json").write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return hashes


def prepare(output: Path, case_id: str | None = None) -> dict:
    output = output.resolve()
    if output.exists():
        raise ValueError("Output must be a new directory; original inputs are immutable")
    items = build_cases()
    if case_id:
        items = [next(item for item in items if item["id"] == case_id)]
    output.mkdir(parents=True)
    hashes = {}
    records = []
    for item in items:
        target = output if case_id else output / item["id"]
        one = write_case(item, target)
        hashes[item["id"]] = one
        records.append({"id": item["id"], "title": item["title"], "kind": item["kind"],
                        "directory": "." if case_id else item["id"],
                        "native_generated": False, "reused_from": item["reused_from"],
                        "source_files": sorted(item["files"]), "request_file": "REQUEST.md"})
    manifest = {"schema_version": 1, "suite": "v08-original-materials",
                "case_count": len(items), "cases": records,
                "inputs_are_immutable": True, "actor_work_policy": "Use a separate output/workspace copy; preserve these source inputs.",
                "oracle_exported": False, "solutions_or_final_diagrams_created": False}
    for name, value in [("cases-manifest.json", manifest), ("source-hashes.json", hashes)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"case_count": len(items), "oracle_exported": False, "source_files_hashed": sum(len(value) for value in hashes.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", help="Prepare only one case, directly in --output")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.case), ensure_ascii=False, indent=2))
