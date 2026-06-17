#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turn_angle 标定 — 在地面上量实际转角，调整 CFG.TURN_CALIB / TRACK_WIDTH_CM。

用法（仓库根目录）：
    python3 test_script/calibrate_turn_angle.py

流程：
  1. 小车摆正，地面贴参考线或用量角器
  2. 按提示依次左转 / 右转，量实际角度
  3. 转不够 → 加大 TURN_CALIB；转过头 → 减小 TURN_CALIB
  4. 角度比例不对 → 微调 TRACK_WIDTH_CM

修改下方 TEST_ANGLES / TURN_SPEED / TURN_STEP 后重跑。
"""

import time

from _common import import_cube

# ========== 临场修改区 ==========
USE_V5 = True
TEST_ANGLES = [90, -90, 45, -45]  # 依次测试的角度（度，正=左转）
TURN_SPEED = 50
TURN_STEP = 0.2
PAUSE_BETWEEN_S = 3.0  # 每次转完后等待人工测量（秒）


def main() -> None:
    lib = import_cube(USE_V5)
    cfg = lib.CFG

    print("=== turn_angle 标定 ===")
    print(f"库: {'cube_v5' if USE_V5 else 'cube_v4'}")
    print(
        f"当前 Config: TURN_CALIB={cfg.TURN_CALIB}, "
        f"TRACK_WIDTH_CM={cfg.TRACK_WIDTH_CM}, "
        f"WHEEL_DIAMETER_CM={cfg.WHEEL_DIAMETER_CM}, "
        f"ENC_FINISH_PULSES={cfg.ENC_FINISH_PULSES}"
    )
    print("摆正车身后按 Enter 开始…")
    input()

    lib.setup(dry_run=False, show_debug=False)
    try:
        for i, angle in enumerate(TEST_ANGLES, 1):
            direction = "左转" if angle > 0 else "右转"
            print(f"\n[{i}/{len(TEST_ANGLES)}] turn_angle({angle}, {TURN_SPEED}, {TURN_STEP}) — {direction}")
            lib.turn_angle(angle, TURN_SPEED, TURN_STEP)
            print(f"请测量实际转角，等待 {PAUSE_BETWEEN_S:.0f}s 后下一项（Ctrl+C 可提前结束）…")
            time.sleep(PAUSE_BETWEEN_S)
    except KeyboardInterrupt:
        print("\n已中断")
    finally:
        lib.cleanup()

    print("\n标定建议：")
    print("  - 系统性转不够：CFG.TURN_CALIB += 0.05~0.1")
    print("  - 系统性转过头：CFG.TURN_CALIB -= 0.05~0.1")
    print("  - 左右转偏差不对称：检查 ENC_SWAP、轮距 TRACK_WIDTH_CM")


if __name__ == "__main__":
    main()
