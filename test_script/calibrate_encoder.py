#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码器读数检查 — 手动转动车轮，观察左右脉冲是否正常累计。

用法：
    python3 test_script/calibrate_encoder.py

用于：
  - 确认接线（LEFT_ENCODER=6, RIGHT_ENCODER=12）
  - 判断是否需要 CFG.ENC_SWAP = True
  - 观察 ENCODER_PULSES_PER_REV 是否合理（转一整圈看增量）
"""

import time

from _common import import_cube

USE_V5 = True
POLL_INTERVAL = 0.15


def main() -> None:
    lib = import_cube(USE_V5)
    cfg = lib.CFG

    print("=== 编码器读数检查 ===")
    print(f"LEFT_ENCODER={cfg.LEFT_ENCODER}, RIGHT_ENCODER={cfg.RIGHT_ENCODER}")
    print(f"ENCODER_PULSES_PER_REV={cfg.ENCODER_PULSES_PER_REV}, ENC_SWAP={cfg.ENC_SWAP}")
    print("手动转动左轮 / 右轮，观察计数；Ctrl+C 结束\n")

    lib.setup(dry_run=False, show_debug=False)
    last_l = last_r = None
    try:
        while True:
            l, r = lib._wheel_counts()
            if last_l is None:
                last_l, last_r = l, r
            dl, dr = l - last_l, r - last_r
            print(
                f"L={l:6d} (Δ{dl:+4d})   R={r:6d} (Δ{dr:+4d})   "
                f"{'← 左轮在转' if dl else ''}{'→ 右轮在转' if dr else ''}",
                end="\r",
            )
            last_l, last_r = l, r
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n结束。若左右计数与所转轮子相反，试 CFG.ENC_SWAP = True")
    finally:
        lib.cleanup()


if __name__ == "__main__":
    main()
