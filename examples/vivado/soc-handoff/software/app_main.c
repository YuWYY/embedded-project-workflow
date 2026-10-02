/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 YuWYY
 * Original A53 application example. Native BSP/build/run: NOT_RUN in v0.5.
 */
#include "xparameters.h"
#include "xgpio.h"
#include "xstatus.h"

#ifndef SDT
#error "This example requires the Vitis SDT driver flow; do not invent DEVICE_ID macros."
#endif
#ifndef XPAR_XGPIO_0_BASEADDR
#error "Verify the real generated GPIO instance mapping before adapting this application."
#endif

enum { CONTROL_CHANNEL = 1, STATUS_CHANNEL = 2 };
enum { COUNT_ENABLE = 1U, COUNT_CLEAR = 2U };

/* Observations only: no successful board test is claimed by this example. */
volatile u32 epw_counter_observation;

int main(void)
{
    XGpio gpio;
    unsigned int sample;
    int status = XGpio_Initialize(&gpio, (UINTPTR)XPAR_XGPIO_0_BASEADDR);
    if (status != XST_SUCCESS) {
        return status;
    }

    XGpio_SetDataDirection(&gpio, CONTROL_CHANNEL, 0U);
    XGpio_SetDataDirection(&gpio, STATUS_CHANNEL, 0xFFFFFFFFU);
    XGpio_DiscreteWrite(&gpio, CONTROL_CHANNEL, COUNT_CLEAR);
    /* MMIO observations give the synchronous clear time to propagate.
     * Actual device-memory attributes/ordering still require target validation.
     */
    for (sample = 0U; sample < 16U; ++sample) {
        epw_counter_observation = XGpio_DiscreteRead(&gpio, STATUS_CHANNEL);
    }
    XGpio_DiscreteWrite(&gpio, CONTROL_CHANNEL, COUNT_ENABLE);
    for (sample = 0U; sample < 1024U; ++sample) {
        epw_counter_observation = XGpio_DiscreteRead(&gpio, STATUS_CHANNEL);
    }
    XGpio_DiscreteWrite(&gpio, CONTROL_CHANNEL, 0U);
    epw_counter_observation = XGpio_DiscreteRead(&gpio, STATUS_CHANNEL);
    return XST_SUCCESS;
}
