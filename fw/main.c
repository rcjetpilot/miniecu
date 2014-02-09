/*
    ChibiOS/RT - Copyright (C) 2006-2013 Giovanni Di Sirio

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

#include "fw_common.h"
#include "th_comm.h"

static THD_WORKING_AREA(wa_comm, 512);

#ifdef USE_NIL_KERNEL
/*
 * Threads static table, one entry per thread. The number of entries must
 * match NIL_CFG_NUM_THREADS.
 */
THD_TABLE_BEGIN
  THD_TABLE_ENTRY(wa_comm, "comm", th_comm, NULL)
  //THD_TABLE_ENTRY(waThread2, "blinker2", Thread2, NULL)
  //THD_TABLE_ENTRY(waThread3, "hello", Thread3, NULL)
THD_TABLE_END
#endif /* USE_NIL_KERNEL */

/*
 * Application entry point.
 */
int main(void) {

	/*
	 * System initializations.
	 * - HAL initialization, this also initializes the configured device drivers
	 *   and performs the board-specific initializations.
	 * - Kernel initialization, the main() function becomes a thread and the
	 *   RTOS is active.
	 */
	halInit();
	chSysInit();

	sdStart(&PBSTX_SD, NULL);

	/* Start threads */
#ifdef USE_RT_KERNEL
	chThdCreateStatic(wa_comm, sizeof(wa_comm), NORMALPRIO, th_comm, NULL);
#endif /* USE_RT_KERNEL */

	while (TRUE) {
		chThdSleepMilliseconds(500);
	}
}
