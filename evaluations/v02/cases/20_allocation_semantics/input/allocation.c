/* Synthetic excerpts mirroring the stated adapter contract, not a complete RTOS. */
uint32_t task_stack[256];
StaticTask_t task_cb;
const osThreadAttr_t worker = { .stack_mem=task_stack, .stack_size=sizeof task_stack, .cb_mem=&task_cb, .cb_size=sizeof task_cb };
static const osEventFlagsAttr_t startup_event = { .name="ready" };
void create_before_scheduler(void) { osThreadNew(Worker,0,&worker); osEventFlagsNew(&startup_event); }
void *timer_adapter(const osTimerAttr_t *attr) {
 void *callback_wrapper=pvPortMalloc(sizeof(TimerCallback_t));
 return attr->cb_mem ? xTimerCreateStatic(callback_wrapper,attr->cb_mem) : xTimerCreate(callback_wrapper);
}
