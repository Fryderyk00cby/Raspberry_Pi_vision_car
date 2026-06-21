#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HSV 临场标定 — 仅 mask 预览（树莓派 + VNC/本地桌面）

独立脚本，不依赖 cube_v4 / cube_v5 主程序。

用法：
  1. 修改下方 LOW/HIGH 常量，运行 python3 HSV_test.py
  2. 看 mask 窗口：方块应为白，背景尽量黑
  3. 不满意 → 改顶部数值 → Ctrl+C 重跑
  4. 按 1/2/3 切换蓝/黄/红预览；按 p 打印全部 HSV 供粘贴到主程序 Config
  5. 按 q 退出

调参经验：
  - S/V 下限：暗场适当降低（如 90→70）；S 过低易误检地面
  - H 范围：先收窄 H 再调 S/V；黄/蓝 H 跨度约 10–15
  - 红色：mask 只在 H≈0 或 H≈180 一侧有效时，只调 RED1 或 RED2
  - 验证：preview 中轮廓稳定、px 明显大于 1000，背景无大块白噪点

需图形界面（cv2.imshow）；SSH 无 X11 时请用 VNC。
"""

from typing import Dict, Optional, Tuple

import cv2
import numpy as np

# ========== 临场修改区（与主程序 Config HSV 字段一一对应）==========
LOW_RED1: Tuple[int, int, int] = (0, 90, 90)
HIGH_RED1: Tuple[int, int, int] = (8, 255, 255)
LOW_RED2: Tuple[int, int, int] = (165, 90, 90)
HIGH_RED2: Tuple[int, int, int] = (180, 255, 255)
LOW_YELLOW: Tuple[int, int, int] = (20, 120, 120)
HIGH_YELLOW: Tuple[int, int, int] = (35, 255, 255)
LOW_BLUE: Tuple[int, int, int] = (100, 120, 70)
HIGH_BLUE: Tuple[int, int, int] = (130, 255, 255)

# 启动时预览颜色："red" / "yellow" / "blue"
PREVIEW_COLOR = "blue"

# 摄像头
CAMERA_ID = 0
CAMERA_BACKEND = "v4l2"  # Linux 摄像头后端；Windows 调试可改为 "auto"
WIDTH = 320
HEIGHT = 240
FPS = 40

# 预览窗口判定用；标定 stop_pixels 时以 cube_v4/v5 调试窗口 px= 为准
FIND_MIN_PIXELS = 1000
MAX_VALID_AREA = 80000

COLOR_MAP = {"1": "blue", "2": "yellow", "3": "red"}
DRAW_COLORS = {"blue": (255, 0, 0), "yellow": (0, 255, 255), "red": (0, 0, 255)}
KERNEL = np.ones((5, 5), np.uint8)


def open_camera(
    camera_id: int = CAMERA_ID,
    width: int = WIDTH,
    height: int = HEIGHT,
    fps: int = FPS,
    backend: str = CAMERA_BACKEND,
):
    """打开摄像头；参数与 cube_v4 / cube_v5 的 CameraThread 一致。"""
    backend = backend.lower()
    tries = []
    if backend in ("v4l2", "auto") and hasattr(cv2, "CAP_V4L2"):
        tries.append(("V4L2", cv2.CAP_V4L2))
    if backend == "auto":
        tries.append(("default", None))
    if not tries:
        tries.append(("default", None))

    for name, api in tries:
        cap = cv2.VideoCapture(camera_id, api) if api is not None else cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        for _ in range(8):
            ok, _ = cap.read()
            if ok:
                print(f"[CAM] id={camera_id} backend={name} {width}x{height}@{fps}")
                return cap
        cap.release()
    raise RuntimeError("无法打开摄像头，请检查 /dev/video* 与 CAMERA_ID")


def mask_color(frame, color: str):
    """HSV 掩膜，阈值逻辑与 cube_v4 / cube_v5 的 Vision.mask_color 一致。"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    if color == "red":
        m1 = cv2.inRange(hsv, np.array(LOW_RED1, np.uint8), np.array(HIGH_RED1, np.uint8))
        m2 = cv2.inRange(hsv, np.array(LOW_RED2, np.uint8), np.array(HIGH_RED2, np.uint8))
        mask = cv2.bitwise_or(m1, m2)
    elif color == "yellow":
        mask = cv2.inRange(hsv, np.array(LOW_YELLOW, np.uint8), np.array(HIGH_YELLOW, np.uint8))
    elif color == "blue":
        mask = cv2.inRange(hsv, np.array(LOW_BLUE, np.uint8), np.array(HIGH_BLUE, np.uint8))
    else:
        raise ValueError(f"未知颜色: {color}")
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, KERNEL)
    return mask


def detect_largest(frame, color: str) -> Optional[Dict]:
    mask = mask_color(frame, color)
    result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = result[-2]
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(largest))
    if area < 1 or area > MAX_VALID_AREA:
        return None

    x, y, w, h = cv2.boundingRect(largest)
    return {
        "color": color,
        "center_x": float(x + w / 2),
        "center_y": float(y + h / 2),
        "pixel_count": int(area),
        "bbox": (x, y, w, h),
    }


def draw_preview(frame, color: str, det: Optional[Dict]) -> np.ndarray:
    out = frame.copy()
    cv2.line(out, (WIDTH // 2, 0), (WIDTH // 2, HEIGHT), (255, 255, 255), 1)
    c = DRAW_COLORS.get(color, (255, 255, 255))
    status = f"{color} | 1=blue 2=yellow 3=red | p=print q=quit"
    cv2.putText(out, status, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    if det is not None:
        x, y, w, h = det["bbox"]
        ok = det["pixel_count"] >= FIND_MIN_PIXELS
        label = f'{det["color"]} px={det["pixel_count"]}' + (" OK" if ok else " LOW")
        cv2.rectangle(out, (x, y), (x + w, y + h), c, 2)
        cv2.circle(out, (int(det["center_x"]), int(det["center_y"])), 5, c, -1)
        cv2.putText(out, label, (x, max(40, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2)
    else:
        cv2.putText(out, "no target", (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)

    cv2.putText(
        out,
        f"{WIDTH}x{HEIGHT} min_px={FIND_MIN_PIXELS}",
        (10, HEIGHT - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (200, 200, 200),
        1,
    )
    return out


def print_hsv_all(current: str) -> None:
    print("\n# ----- 复制到主程序 Config -----")
    print(f"    LOW_RED1: Tuple[int, int, int] = {LOW_RED1}")
    print(f"    HIGH_RED1: Tuple[int, int, int] = {HIGH_RED1}")
    print(f"    LOW_RED2: Tuple[int, int, int] = {LOW_RED2}")
    print(f"    HIGH_RED2: Tuple[int, int, int] = {HIGH_RED2}")
    print(f"    LOW_YELLOW: Tuple[int, int, int] = {LOW_YELLOW}")
    print(f"    HIGH_YELLOW: Tuple[int, int, int] = {HIGH_YELLOW}")
    print(f"    LOW_BLUE: Tuple[int, int, int] = {LOW_BLUE}")
    print(f"    HIGH_BLUE: Tuple[int, int, int] = {HIGH_BLUE}")
    print(f"# 当前预览: {current}\n")


def main() -> None:
    color = PREVIEW_COLOR.strip().lower()
    if color not in ("blue", "yellow", "red"):
        raise ValueError(f'PREVIEW_COLOR 须为 "blue" / "yellow" / "red"，当前: {PREVIEW_COLOR}')

    cap = open_camera()
    print(f"[HSV_test] 预览 {color} | 1=blue 2=yellow 3=red | p=print | q=quit")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            mask = mask_color(frame, color)
            det = detect_largest(frame, color)
            preview = draw_preview(frame, color, det)

            cv2.imshow("mask", mask)
            cv2.imshow("preview", preview)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("p"):
                print_hsv_all(color)
            ch = chr(key) if 32 <= key < 127 else ""
            if ch in COLOR_MAP:
                color = COLOR_MAP[ch]
                print(f"[HSV_test] 切换预览 -> {color}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
