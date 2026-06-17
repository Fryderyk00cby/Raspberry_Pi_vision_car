#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
forward_pid 直行标定 — 按时间直行并观察是否跑偏，调 step / interval。

用法：
    python3 test_script/calibrate_forward_pid.py

说明：
  forward_pid 按 duration 停车，不按厘米停。标定目标是找到合适的
  left/right 速度、step、interval、duration 组合，使直行段长度与跑偏可控。

修改下方参数后重跑；可在地面贴起点线，用尺量实际前进距离。
"""

import time

from _common import import_cube

# ========== 临场修改区 ==========
USE_V5 = True
LEFT_SPEED = 40.0
RIGHT_SPEED = 40.0
STEP = 0.5
INTERVAL = 0.05
DURATION = 1.0  # 秒；按赛道段逐步加长测试
REPEAT = 3  # 连续跑几次，观察重复性
PAUSE_BETWEEN_S = 2.0


def main() -> None:
    lib = import_cube(USE_V5)

    print("=== forward_pid 直行标定 ===")
    print(
        f"参数: L={LEFT_SPEED}, R={RIGHT_SPEED}, "
        f"step={STEP}, interval={INTERVAL}, duration={DURATION}s, repeat={REPEAT}"
    )
    print("摆正后按 Enter 开始…")
    input()

    lib.setup(dry_run=False, show_debug=False)
    try:
        for i in range(1, REPEAT + 1):
            print(f"\n[{i}/{REPEAT}] forward_pid 开始")
            lib.forward_pid(LEFT_SPEED, RIGHT_SPEED, STEP, INTERVAL, DURATION)
            if i < REPEAT:
                print(f"摆正车身，{PAUSE_BETWEEN_S:.0f}s 后下一次…")
                time.sleep(PAUSE_BETWEEN_S)
    except KeyboardInterrupt:
        print("\n已中断")
    finally:
        lib.cleanup()

    print("\n标定建议：")
    print("  - 向一侧偏：增大 step，或略调左右初始速度差")
    print("  - 抖动：减小 step 或增大 interval")
    print("  - 段长：改 duration 传参（非 Config）")


if __name__ == "__main__":
    main()
