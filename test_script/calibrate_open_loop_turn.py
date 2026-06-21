#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开环转弯标定 — 调 turn_left / turn_right 的 duration 与 wheel_speed。

用法：
    python3 test_script/calibrate_open_loop_turn.py

适用于开环转弯标定；主流程推荐 calibrate_turn_angle.py（编码器 turn_angle）。
"""

import time

from _common import import_cube

# ========== 临场修改区 ==========
USE_V5 = True
TESTS = [
    ("左转", "turn_left", 0.2, 60),
    ("右转", "turn_right", 0.2, 60),
    ("左转（慢）", "turn_left", 0.25, 45),
]
PAUSE_BETWEEN_S = 3.0


def main() -> None:
    lib = import_cube(USE_V5)

    print("=== 开环转弯标定 ===")
    for label, _, duration, speed in TESTS:
        print(f"  {label}: duration={duration}, wheel_speed={speed}")
    print("摆正后按 Enter 开始…")
    input()

    lib.setup(dry_run=False, show_debug=False)
    try:
        for i, (label, fn_name, duration, speed) in enumerate(TESTS, 1):
            fn = getattr(lib, fn_name)
            print(f"\n[{i}/{len(TESTS)}] {label} — {fn_name}({duration}, {speed})")
            fn(duration, speed)
            print(f"请测量角度，等待 {PAUSE_BETWEEN_S:.0f}s…")
            time.sleep(PAUSE_BETWEEN_S)
    except KeyboardInterrupt:
        print("\n已中断")
    finally:
        lib.cleanup()

    print("\n标定建议：量出约 90° 对应的 duration，写入比赛 main 传参。")


if __name__ == "__main__":
    main()
