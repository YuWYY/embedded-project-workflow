/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#ifndef RTOS_OWNERSHIP_APP_H
#define RTOS_OWNERSHIP_APP_H
void RtosApp_CheckCreated(void);
void Producer_Entry(void *argument);
void Consumer_Entry(void *argument);
#endif
