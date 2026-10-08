#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Five original, coordinate-edited layout references, not project defaults.

Edit the drawing functions and regenerate. No model import, automatic layout,
vendor software, hardware access or dependency installation is performed.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from planning_canvas import Canvas, INK, MUTED, BORDER, DATA, CONTROL, CLOCK, RESET


def page(title, subtitle):
    c = Canvas(width=1600, height=1000)
    c.text(40, 28, title, size=36, bold=True)
    c.text(42, 83, subtitle, size=23, color=MUTED)
    c.wire([(40, 134), (1560, 134)], color=BORDER, arrow=False, width=1)
    return c


def block(c, x, y, w, h, title, detail, size=25):
    # Preserve the established template coordinates while using the reusable
    # primitive. No wrapping or layout is inferred from a project's contents.
    c.block(x, y, w, h, title, detail, title_size=size, body_size=20,
            padding=15, gap=38-size)


def footer(c, note):
    c.wire([(40, 907), (1560, 907)], color=BORDER, arrow=False, width=1)
    for x, color, label in [(45, DATA, '数据'), (270, CONTROL, '控制'), (495, CLOCK, '时钟'), (720, RESET, '复位')]:
        c.wire([(x, 938), (x+58, 938)], color=color)
        c.text(x+75, 922, label, size=22)
    c.text(990, 922, '虚线仅表示已命名的分组 / 时钟域', size=22, color=MUTED)
    c.text(42, 964, note, size=19, color=MUTED)


def chip_pin_layout():
    c = page('① 引脚功能分配｜芯片边缘布局参考',
             '全部信号名称和 PIN 标签均为示例占位；实际图必须从当前原生配置与原理图核对。')
    c.rect(605, 205, 390, 660, stroke=INK, line_width=2.5)
    for x in range(650, 960, 45):
        c.wire([(x, 190), (x, 205)], color=BORDER, arrow=False, width=2)
        c.wire([(x, 865), (x, 880)], color=BORDER, arrow=False, width=2)
    c.text(800, 408, 'MCU / FPGA', size=38, bold=True, anchor='center')
    c.text(800, 472, '型号 / 封装：待确认', size=26, anchor='center')
    c.text(800, 528, '原生配置负责实际分配', size=23, color=MUTED, anchor='center')
    c.text(800, 575, '图中位置不代表物理脚序', size=23, color=MUTED, anchor='center')
    rows = [(310, '传感器输入', '采样功能：待确认', 'PIN_A（占位）', 'adc_in（示例）', DATA),
            (535, '外部时钟源', '频率 / 电压：待确认', 'PIN_B（占位）', 'clk_in（示例）', CLOCK),
            (760, '复位来源', '极性 / 电平：待确认', 'PIN_C（占位）', 'reset_n（示例）', RESET)]
    for y, title, detail, pin, signal, color in rows:
        block(c, 40, y-55, 300, 110, title, detail)
        c.wire([(340, y), (605, y)], color=color)
        c.text(472, y-59, pin+'\n'+signal, size=19, color=color, anchor='center')
    rows = [(310, '执行器接口', '极性 / 安全态：待确认', 'PIN_D（占位）', 'pwm_out（示例）', CONTROL),
            (535, '通信收发器', '方向 / 速率：待确认', 'PIN_E（占位）', 'uart_tx（示例）', DATA),
            (760, '状态指示', '有效电平：待确认', 'PIN_F（占位）', 'status（示例）', CONTROL)]
    for y, title, detail, pin, signal, color in rows:
        block(c, 1260, y-55, 300, 110, title, detail)
        c.wire([(995, y), (1260, y)], color=color)
        c.text(1127, y-59, pin+'\n'+signal, size=19, color=color, anchor='center')
    footer(c, '填写实际端口、封装脚号、方向、电平和复用；当前模板没有已确认的引脚事实，也不证明硬件连通。')
    return c


def baremetal_execution():
    c = page('② 模块执行逻辑｜裸机循环、IRQ 与硬件回调',
             '示例结构：主循环顺序执行；硬件独立推进；IRQ 可抢占主循环，回调上下文必须注明。')
    c.scope(40, 165, 1520, 185, '主循环 main：顺序运行；循环一次的 CPU 时间待测')
    block(c, 90, 226, 325, 92, '读取事件 / 最新样本', '每轮执行；有新数据才处理')
    block(c, 590, 226, 355, 92, '应用状态机', '条件成立时更新状态')
    block(c, 1140, 226, 350, 92, '后台工作', '非阻塞步骤；完成后回到循环')
    c.wire([(415, 268), (590, 268)], color=CONTROL)
    c.text(502, 234, '事件标志', size=19, color=CONTROL, anchor='center')
    c.wire([(945, 268), (1140, 268)], color=CONTROL)
    c.text(1042, 234, '下一步骤', size=19, color=CONTROL, anchor='center')
    c.wire([(1315, 318), (1315, 334), (252, 334), (252, 318)], color=CONTROL)
    c.scope(40, 389, 1520, 232, 'IRQ / 回调上下文：在中断中执行；仅做有界工作，禁止无界等待')
    block(c, 90, 451, 325, 120, 'DMA / 外设 IRQ', '触发：完成标志或错误标志')
    block(c, 590, 451, 355, 120, '驱动完成回调', '本例由 IRQ 调用\n确认实际回调上下文')
    block(c, 1140, 451, 350, 120, '发布缓冲区 / 事件', '交接后立即返回\n共享状态需要一致性约定')
    c.wire([(415, 503), (590, 503)], color=CONTROL)
    c.text(502, 467, '驱动分派', size=19, color=CONTROL, anchor='center')
    c.wire([(945, 503), (1140, 503)], color=DATA)
    c.text(1042, 467, '样本就绪', size=19, color=DATA, anchor='center')
    c.wire([(1315, 451), (1315, 378), (300, 378), (300, 318)], color=DATA)
    c.text(820, 353, '交接数据 / 事件；不是直接调用主循环', size=19, color=DATA, anchor='center')
    c.text(78, 587, '优先级与最大 IRQ 持续时间：待确认。共享缓冲的所有权、覆盖规则及临界区：待确认。', size=20, color=MUTED)
    c.scope(40, 661, 1520, 216, '硬件：定时器、采样与 DMA 可独立于 CPU 推进')
    block(c, 90, 723, 325, 110, '定时器触发', '触发周期：待确认')
    block(c, 590, 723, 355, 110, 'ADC / 外设采样', '触发边沿到来时启动')
    block(c, 1140, 723, 350, 110, 'DMA 写缓冲区', '传输完成时置位 IRQ')
    c.wire([(415, 775), (590, 775)], color=CONTROL)
    c.text(502, 741, '触发', size=19, color=CONTROL, anchor='center')
    c.wire([(945, 775), (1140, 775)], color=DATA)
    c.text(1042, 741, '采样值', size=19, color=DATA, anchor='center')
    c.wire([(1315, 833), (1315, 860), (25, 860), (25, 584), (252, 584), (252, 571)], color=CONTROL)
    c.text(800, 882, '完成 IRQ：硬件触发软件入口', size=18, color=CONTROL, anchor='center')
    footer(c, '规划图不等于中断时延或实时性证据；用当前工程的 IRQ 优先级、回调调用链及实测预算替换占位。')
    return c


def rtos_execution():
    c = page('② 模块执行逻辑｜RTOS 任务与交接',
             '全部任务与数值仅为示例；本图示例调度约定：抢占式、优先级数值越大越高。')
    c.text(42, 165, '优先级解释必须从当前内核确认；任务并发不表示多个任务同时占用单核 CPU。', size=23, color=MUTED)
    c.scope(40, 219, 640, 620, '任务：触发、CPU 执行预算、阻塞等待分别记录')
    c.rect(65, 285, 590, 156)
    c.text(85, 300, 'AcquisitionTask｜优先级 4（示例）', size=26, bold=True)
    c.text(85, 343, '触发：DMA 完成通知；周期由硬件决定', size=22)
    c.text(85, 380, 'CPU 预算：待测；阻塞：等待通知（上限待定）', size=21, color=MUTED)
    c.text(85, 410, '截止期：待确认；发布后归还缓冲区所有权', size=21, color=MUTED)
    c.rect(65, 468, 590, 156)
    c.text(85, 483, 'ControlTask｜优先级 3（示例）', size=26, bold=True)
    c.text(85, 526, '触发：每 2 ms 释放一次（示例）', size=22)
    c.text(85, 563, 'CPU 预算：待测；阻塞：等待下次周期释放', size=21, color=MUTED)
    c.text(85, 593, '截止期：待确认；超期处理策略：待确认', size=21, color=MUTED)
    c.rect(65, 651, 590, 156)
    c.text(85, 666, 'LoggerTask｜优先级 1（示例）', size=26, bold=True)
    c.text(85, 709, '触发：队列有数据时运行', size=22)
    c.text(85, 746, 'CPU 预算：待测；阻塞：等待队列（上限待定）', size=21, color=MUTED)
    c.text(85, 776, '截止期：待确认；禁止阻塞高优先级控制链', size=21, color=MUTED)
    c.scope(1010, 219, 550, 620, '事件 / 队列 / 外设：写清所有权及满空策略')
    block(c, 1050, 285, 465, 118, 'DMA 完成 ISR → 任务通知', '本例 ISR 使用内核许可的 FromISR 接口\nIRQ 优先级与内核调用限制：待确认', size=24)
    c.wire([(1050, 335), (655, 335)], color=CONTROL)
    c.text(832, 301, '唤醒 / 缓冲区标识', size=21, color=CONTROL, anchor='center')
    block(c, 1050, 455, 465, 146, 'SampleQueue（示例）', 'AcquisitionTask 写 → ControlTask 读\n容量 4（示例）；满时策略：待确认\n读取等待上限：待确认', size=24)
    c.wire([(655, 406), (895, 406), (895, 487), (1050, 487)], color=DATA)
    c.text(830, 372, '发布样本', size=21, color=DATA, anchor='center')
    c.wire([(1050, 556), (655, 556)], color=DATA)
    c.text(832, 521, '读取最新 / 下一样本', size=21, color=DATA, anchor='center')
    block(c, 1050, 653, 465, 146, 'LogQueue（示例）', 'ControlTask 写 → LoggerTask 读\n容量：待确认；满时策略：待确认\n等待 / 丢弃 / 降采样需明确选择', size=24)
    c.wire([(655, 597), (905, 597), (905, 687), (1050, 687)], color=DATA)
    c.text(825, 610, '发送状态快照', size=21, color=DATA, anchor='center')
    c.wire([(1050, 750), (655, 750)], color=DATA)
    c.text(832, 715, '取出日志', size=21, color=DATA, anchor='center')
    c.text(42, 859, 'CPU 执行时间 ≠ 周期 ≠ 阻塞等待时间；响应时间还受抢占、IRQ、资源竞争与优先级反转影响。', size=23, color=MUTED)
    footer(c, '示例不是调度分析结果；栈、任务总负载、最坏执行时间、阻塞上限和优先级继承需要工程证据。')
    return c


def fpga_single_domain():
    c = page('② 模块并行执行逻辑｜FPGA 单时钟域',
             '示例：各模块持续并行；模块内写明每拍、使能或 valid / ready 条件，不绘 CPU 任务时间片。')
    c.scope(225, 183, 1335, 690, '时钟域 clk_sys：50 MHz / 20 ns（示例）；所有寄存器由该域时钟驱动')
    c.text(250, 238, '域复位 rst_sys：高有效（示例）；来源 / 释放同步约定必须从实际 RTL 确认。', size=22, color=MUTED)
    block(c, 40, 441, 145, 118, '外部输入', 'enable_raw\n异步控制', size=23)
    block(c, 280, 441, 270, 156, '输入同步', 'input_sync\n每拍采样同步链\n不直接同步多位数据', size=26)
    block(c, 780, 441, 290, 156, '计数 / 数据处理', 'counter_core\n每拍判断 enable_sync\n为 1 更新；为 0 保持', size=25)
    block(c, 1275, 345, 245, 149, '状态输出', 'status_reg\n每拍采样计数位\n输出寄存状态', size=25)
    block(c, 1275, 652, 245, 160, '快照发送', 'status_stream\n每 20 ms 请求（示例）\nvalid && ready 时传输', size=25)
    c.wire([(185, 500), (280, 500)], color=CONTROL)
    c.wire([(550, 500), (780, 500)], color=CONTROL)
    c.text(665, 462, 'enable_sync', size=21, color=CONTROL, anchor='center')
    c.wire([(1070, 520), (1175, 520)], color=DATA, arrow=False)
    c.wire([(1175, 520), (1175, 423), (1275, 423)], color=DATA)
    c.wire([(1175, 520), (1175, 726), (1275, 726)], color=DATA)
    c.dot(1175, 520)
    c.text(1155, 539, 'counter', size=19, color=DATA, anchor='right')
    c.text(1155, 568, '[31:0]', size=19, color=DATA, anchor='right')
    # Shared clock/reset are domain annotations; no arrows end at the contour.
    c.text(280, 690, '20 ms 仅为业务周期；各模块始终并行。', size=23, color=MUTED)
    c.text(280, 739, '未就绪时保持 valid 与载荷；满 / 忙处理待定义。', size=22, color=MUTED)
    c.text(250, 832, '黑点 = 真实连接；交叉无点 = 不连接。', size=21, color=MUTED)
    footer(c, '示例参数待替换；图示不等于 RTL 仿真、CDC、时序或板级验证。')
    return c


def fpga_dual_domain_fifo():
    c = page('② 模块并行执行逻辑｜FPGA 双时钟域与异步 FIFO',
             '所有参数与接口均为示例；使用实际 FIFO 的端口、满空含义及复位协议替换本图。')
    c.scope(40, 180, 420, 690, '写时钟域 clk_wr：80 MHz（示例）')
    c.scope(1140, 180, 420, 690, '读时钟域 clk_rd：50 MHz（示例）')
    c.text(65, 234, '12.5 ns；rst_wr 高有效（示例）', size=22, color=MUTED)
    c.text(1155, 234, '20 ns；rst_rd 高有效（示例）', size=22, color=MUTED)
    block(c, 80, 407, 370, 187, '写侧生产模块', 'producer\n每拍检查 in_valid && in_ready\n条件成立才接收 / 写入数据\n未就绪：保持载荷或按协议丢弃', size=26)
    block(c, 1150, 407, 370, 187, '读侧消费模块', 'consumer\n每拍检查 out_valid && out_ready\n条件成立才读取 / 消费数据\n未就绪：停止取数，不越过空边界', size=26)
    c.rect(630, 371, 340, 276, stroke=INK, line_width=2.5)
    c.text(800, 390, '异步 FIFO', size=30, bold=True, anchor='center')
    c.text(800, 436, '跨域队列 / 边界', size=24, color=DATA, anchor='center')
    c.text(800, 481, '写时钟域：wr_clk / wr_reset', size=20, anchor='center')
    c.text(800, 521, '读时钟域：rd_clk / rd_reset', size=20, anchor='center')
    c.text(800, 566, '位宽 / 深度：待确认', size=22, color=MUTED, anchor='center')
    c.text(800, 606, '不使用直接多位同步器替代', size=20, color=MUTED, anchor='center')
    c.wire([(450, 455), (630, 455)], color=DATA)
    c.text(540, 416, 'wr_data / wr_en', size=19, color=DATA, anchor='center')
    c.wire([(630, 555), (450, 555)], color=CONTROL)
    c.text(540, 571, 'full / in_ready', size=19, color=CONTROL, anchor='center')
    c.wire([(970, 455), (1150, 455)], color=DATA)
    c.text(1060, 416, 'rd_data / valid', size=19, color=DATA, anchor='center')
    c.wire([(1150, 555), (970, 555)], color=CONTROL)
    c.text(1060, 571, 'rd_en / ready', size=19, color=CONTROL, anchor='center')
    c.text(65, 302, 'clk_wr', size=22, color=CLOCK)
    c.wire([(180, 318), (710, 318), (710, 371)], color=CLOCK)
    c.text(740, 323, 'wr_clk', size=18, color=CLOCK)
    c.text(1180, 302, 'clk_rd', size=22, color=CLOCK)
    c.wire([(1170, 318), (890, 318), (890, 371)], color=CLOCK)
    c.text(918, 323, 'rd_clk', size=18, color=CLOCK)
    c.text(65, 687, 'rst_wr', size=22, color=RESET)
    c.wire([(180, 701), (710, 701), (710, 647)], color=RESET)
    c.text(735, 663, 'wr_reset', size=18, color=RESET)
    c.text(1180, 687, 'rst_rd', size=22, color=RESET)
    c.wire([(1170, 701), (890, 701), (890, 647)], color=RESET)
    c.text(915, 663, 'rd_reset', size=18, color=RESET)
    c.text(65, 758, '写入边界（示例）：\nin_ready = !full && !wr_reset_busy\n复位 / 忙时禁止写入', size=20, color=MUTED)
    c.text(1155, 758, '读取边界（示例）：\nout_valid = !empty && !rd_reset_busy\n复位 / 忙时禁止读取', size=19, color=MUTED)
    c.text(800, 751, '示例采用 FWFT 风格；标准读模式\n需按实际读延迟生成 valid。\n双方复位完成后才恢复传输。', size=21, color=MUTED, anchor='center')
    footer(c, '复位端口数及协调、同步释放、busy 时序必须遵循实际 IP 契约；该规划图不是 CDC 或复位正确性证明。')
    return c


TEMPLATES = (
    ('01-chip-pin-layout', chip_pin_layout),
    ('02-baremetal-execution', baremetal_execution),
    ('03-rtos-execution', rtos_execution),
    ('04-fpga-single-domain', fpga_single_domain),
    ('05-fpga-dual-domain-fifo', fpga_dual_domain_fifo),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Caller-selected output directory')
    parser.add_argument('--format', choices=('svg', 'both'), default='svg')
    parser.add_argument('--font', type=Path, help='Existing font supporting all labels; needed only for PNG')
    args = parser.parse_args(argv)
    for stem, factory in TEMPLATES:
        result = factory().save(args.output, stem, format=args.format, font=args.font)
        print(result['svg'])
        if result['png'] is not None:
            print(result['png'])
        if result['png_gap']:
            print(f'{stem}: {result["png_gap"]}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
