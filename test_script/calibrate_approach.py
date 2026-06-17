#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
靠近标定 — 搜色后 PID 靠近，在调试窗口看 px= 轮廓面积，确定 stop_pixels。

用法：
    python3 test_script/calibrate_approach.py

需图形界面（VNC 或本地桌面）。调试窗口中的 px 即为 stop_pixels 参考值。
颜色 HSV 请先用根目录 HSV_test.py 标定。
"""

from _common import import_cube

# ========== 临场修改区 ==========
USE_V5 = True
COLOR = "blue"  # blue / yellow / red
SEARCH_PWM = -40
SEARCH_INTERVAL = 0.3
USE_LEFT_WHEEL = False  # 仅 v5 有效
FORWARD_SPEED = 28
STOP_PIXELS = 15000  # 先设偏大，观察窗口 px 后再改小
PID = dict(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)


def main() -> None:
    lib = import_cube(USE_V5)
    pid = lib.PidParams(**PID)

    print("=== 靠近标定 (approach_target) ===")
    print(f"颜色: {COLOR}, stop_pixels={STOP_PIXELS}")
    print("观察调试窗口 px=；合适停距时记下该数值作为 stop_pixels")
    print("按 Enter 开始搜色…")
    input()

    lib.setup(dry_run=False, show_debug=True)
    try:
        if USE_V5:
            found = lib.search_color(
                SEARCH_PWM, SEARCH_INTERVAL, COLOR, use_left_wheel=USE_LEFT_WHEEL
            )
        else:
            found = lib.search_color(SEARCH_PWM, SEARCH_INTERVAL, COLOR)
        if not found:
            print(f"[失败] 未找到 {COLOR}，请调 HSV 或 search_color 参数")
            return

        print(f"已找到 {COLOR}，开始靠近…")
        ok = lib.approach_target(COLOR, FORWARD_SPEED, pid, stop_pixels=STOP_PIXELS)
        print("靠近成功" if ok else "靠近失败（超时或丢目标）")
    except KeyboardInterrupt:
        print("\n已中断")
    finally:
        lib.cleanup()

    print("\n将记下的 px 写入 main 里 approach_target(..., stop_pixels=...) 传参。")


if __name__ == "__main__":
    main()
