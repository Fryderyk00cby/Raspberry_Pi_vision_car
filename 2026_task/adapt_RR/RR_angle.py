#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
魔方绕桩任务 — 可拼接函数库 v4+（OpenCV + RPi.GPIO）

在 cube_v4 基础上仅新增 turn_angle（编码器按角度转弯），其余 API 与 v4 相同。
  含 forward_pid、search_color、turn_angle 等。
速度参数均为 PWM 占空比，范围 -100~100；负值表示该轮反转（后退）。

turn_angle 即插即用（setup 后直接调用）：
    turn_angle(90)       # 左转 90°，默认 speed=50, step=0.2
    turn_angle(-90)      # 右转 90°
    turn_left(0.2, 60)   # 仍可继续用 v4 开环转弯

摄像头（参考 text_alms）：默认 320x240 @ 40fps，降低分辨率以提升树莓派帧率。
  换分辨率后须同步缩放面积阈值与横向像素容差，见 Config 内注释。

实时画面（与 reference_pj/main.py 一致）：9
  - 树莓派本地：Config.SHOW_DEBUG = True，调用 show_debug()，用 cv2.imshow 看窗口。
  - 电脑远程看画面（任选其一）：
      1) SSH 带 X11：ssh -X pi@<IP>，再运行你的脚本（需树莓派有桌面或 X 转发）。
      2) VNC：树莓派开 VNC，电脑用 VNC 客户端连上去，imshow 窗口在远程桌面里。
      3) 无图形界面时：可把 SHOW_DEBUG 关掉，仅用 print 日志；或自行加 mjpg-streamer 等推流。
"""

import math
import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

import cv2
import numpy as np

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None


# =============================================================================
# 配置区：引脚、HSV、摄像头等（按现场修改）
# =============================================================================

@dataclass
class Config:
    DRY_RUN: bool = False
    SHOW_DEBUG: bool = True
    DEBUG_WINDOW: str = "cube debug"

    CAMERA_ID: int = 0
    CAMERA_BACKEND: str = "v4l2"
    # 降分辨率换帧率（参考 text_alms）；相对 640x480 画面面积约 ×0.25
    WIDTH: int = 320
    HEIGHT: int = 240
    FPS: int = 40

    LEFT_PWM: int = 13
    LEFT_IN1: int = 26
    LEFT_IN2: int = 19
    RIGHT_PWM: int = 16
    RIGHT_IN1: int = 20
    RIGHT_IN2: int = 21
    PWM_FREQ: int = 80

    # 霍尔编码器（参考 auto_back.py：LS=6, RS=12）
    LEFT_ENCODER: int = 6
    RIGHT_ENCODER: int = 12
    ENCODER_PULSES_PER_REV: float = 585.0
    FORWARD_PID_INTERVAL: float = 0.01

    # turn_angle 专用（首次上车按地面标定 TURN_CALIB / TRACK_WIDTH_CM）
    WHEEL_DIAMETER_CM: float = 6.5
    TRACK_WIDTH_CM: float = 14.0
    TURN_CALIB: float = 0.5
    ENC_FINISH_PULSES: int = 4
    ENC_TIMEOUT_S: float = 6.0
    ENC_LOOP_INTERVAL: float = 0.01
    ENC_SWAP: bool = False
    ENC_DRY_TURN_DEG_PER_SEC: float = 90.0

    SWAP_WHEELS: bool = False
    INVERT_LEFT: bool = False
    INVERT_RIGHT: bool = False

    LOW_RED1: Tuple[int, int, int] = (0, 90, 90)
    HIGH_RED1: Tuple[int, int, int] = (8, 255, 255)
    LOW_RED2: Tuple[int, int, int] = (165, 90, 90)
    HIGH_RED2: Tuple[int, int, int] = (180, 255, 255)
    LOW_YELLOW: Tuple[int, int, int] = (20, 120, 120)
    HIGH_YELLOW: Tuple[int, int, int] = (35, 255, 255)
    LOW_BLUE: Tuple[int, int, int] = (100, 120,70)
    HIGH_BLUE: Tuple[int, int, int] = (130, 255, 255)

    # 轮廓面积阈值（随分辨率缩放；640x480 时分别为 330000 / 4000 / 85000）
    MAX_VALID_AREA: int = 80000
    APPROACH_STOP_PIXELS: int = 21000

    # search_color 总搜索超时（秒）
    SEARCH_FULL_ROTATION_TIME: float = 10
    # search_color：每步停车后等待画面稳定再识别（秒）
    SEARCH_COLOR_SETTLE_TIME: float = 0.3

    APPROACH_LOST_BACKUP_FRAMES: int = 10
    APPROACH_TIMEOUT: float = 15.0
    APPROACH_MIN_DELTA: float = 6.0
    APPROACH_MAX_DELTA: float = 18.0


CFG = Config()

# PID 调参：可用元组 (kp, ki, kd) 或本 dataclass
@dataclass
class PidParams:
    kp: float
    ki: float
    kd: float
    min_delta: float = 6.0
    max_delta: float = 18.0


PidInput = Union[PidParams, Tuple[float, float, float]]


def _parse_pid(pid: PidInput) -> PidParams:
    if isinstance(pid, PidParams):
        return pid
    kp, ki, kd = pid
    return PidParams(kp=kp, ki=ki, kd=kd)


def _norm_color(color: str) -> str:
    c = color.strip().lower()
    if c in ("blue", "yellow", "red", "蓝", "黄", "红"):
        mapping = {"蓝": "blue", "黄": "yellow", "红": "red"}
        return mapping.get(c, c)
    raise ValueError(f"未知颜色: {color}，请用 blue / yellow / red")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def now() -> float:
    return time.time()


# =============================================================================
# PID
# =============================================================================

class PID:
    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.last_error = 0.0
        self.err_sum = 0.0
        self.last_time = None

    def reset(self) -> None:
        self.last_error = 0.0
        self.err_sum = 0.0
        self.last_time = None

    def feedback(self, error: float) -> float:
        t = now()
        if self.last_time is None:
            dt = 0.02
        else:
            dt = max(1e-3, t - self.last_time)
        self.err_sum += error * dt
        derivative = (error - self.last_error) / dt
        out = self.kp * error + self.ki * self.err_sum + self.kd * derivative
        self.last_error = error
        self.last_time = t
        return out


# =============================================================================
# 摄像头线程
# =============================================================================

def open_camera(cfg: Config):
    backend = cfg.CAMERA_BACKEND.lower()
    tries = []
    if backend in ("v4l2", "auto") and hasattr(cv2, "CAP_V4L2"):
        tries.append(("V4L2", cv2.CAP_V4L2))
    if backend == "auto":
        tries.append(("default", None))
    if not tries:
        tries.append(("default", None))

    for name, api in tries:
        cap = cv2.VideoCapture(cfg.CAMERA_ID, api) if api is not None else cv2.VideoCapture(cfg.CAMERA_ID)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, cfg.FPS)
        for _ in range(8):
            ok, _ = cap.read()
            if ok:
                print(f"[CAM] id={cfg.CAMERA_ID} backend={name}")
                return cap
        cap.release()
    raise RuntimeError("无法打开摄像头，请检查 /dev/video* 与 CAMERA_ID")


class CameraThread:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cap = open_camera(cfg)
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        t0 = now()
        while self.get_frame() is None and now() - t0 < 2.0:
            time.sleep(0.02)

    def _loop(self) -> None:
        while self.running:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def stop(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None


# =============================================================================
# 视觉识别
# =============================================================================

class Vision:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.kernel = np.ones((5, 5), np.uint8)

    def mask_color(self, frame, color: str):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if color == "red":
            m1 = cv2.inRange(hsv, np.array(self.cfg.LOW_RED1, np.uint8), np.array(self.cfg.HIGH_RED1, np.uint8))
            m2 = cv2.inRange(hsv, np.array(self.cfg.LOW_RED2, np.uint8), np.array(self.cfg.HIGH_RED2, np.uint8))
            mask = cv2.bitwise_or(m1, m2)
        elif color == "yellow":
            mask = cv2.inRange(
                hsv, np.array(self.cfg.LOW_YELLOW, np.uint8), np.array(self.cfg.HIGH_YELLOW, np.uint8)
            )
        elif color == "blue":
            mask = cv2.inRange(hsv, np.array(self.cfg.LOW_BLUE, np.uint8), np.array(self.cfg.HIGH_BLUE, np.uint8))
        else:
            raise ValueError(color)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
        return mask

    def detect(self, frame, color: str, min_pixels: int) -> Optional[Dict]:
        """
        min_pixels：掩膜中最大连通色块像素数（cv2.contourArea），达到才算识别成功。
        """
        mask = self.mask_color(frame, color)
        result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = result[-2]
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))
        if area < min_pixels or area > self.cfg.MAX_VALID_AREA:
            return None

        x, y, w, h = cv2.boundingRect(largest)
        return {
            "color": color,
            "center_x": float(x + w / 2),
            "center_y": float(y + h / 2),
            "area": area,
            "pixel_count": int(area),
            "bbox": (x, y, w, h),
            "mask": mask,
            "contour": largest,
        }

    def draw(self, frame, det: Optional[Dict], state_text: str = ""):
        out = frame.copy()
        cv2.line(out, (self.cfg.WIDTH // 2, 0), (self.cfg.WIDTH // 2, self.cfg.HEIGHT), (255, 255, 255), 1)
        colors = {"blue": (255, 0, 0), "yellow": (0, 255, 255), "red": (0, 0, 255)}
        if det is not None:
            c = colors.get(det["color"], (255, 255, 255))
            x, y, w, h = det["bbox"]
            cv2.rectangle(out, (x, y), (x + w, y + h), c, 2)
            cv2.circle(out, (int(det["center_x"]), int(det["center_y"])), 5, c, -1)
            cv2.putText(
                out,
                f'{det["color"]} px={det["pixel_count"]}',
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                c,
                2,
            )
        if state_text:
            cv2.putText(out, state_text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(
            out,
            f"{self.cfg.WIDTH}x{self.cfg.HEIGHT}",
            (10, self.cfg.HEIGHT - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (200, 200, 200),
            1,
        )
        return out


# =============================================================================
# 电机（PWM 占空比）
# =============================================================================

class Car:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.dry = cfg.DRY_RUN or GPIO is None
        self.pwm_left = None
        self.pwm_right = None

    def setup(self) -> None:
        if self.dry:
            print("[DRY_RUN] 仅打印电机指令，不驱动 GPIO")
            return
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        pins = [
            self.cfg.LEFT_PWM,
            self.cfg.LEFT_IN1,
            self.cfg.LEFT_IN2,
            self.cfg.RIGHT_PWM,
            self.cfg.RIGHT_IN1,
            self.cfg.RIGHT_IN2,
        ]
        GPIO.setup(pins, GPIO.OUT)
        self.pwm_left = GPIO.PWM(self.cfg.LEFT_PWM, self.cfg.PWM_FREQ)
        self.pwm_right = GPIO.PWM(self.cfg.RIGHT_PWM, self.cfg.PWM_FREQ)
        self.pwm_left.start(0)
        self.pwm_right.start(0)
        self.stop()

    def _set_motor(self, pwm, in1: int, in2: int, speed: float, invert: bool) -> None:
        speed = clamp(speed, -100, 100)
        if invert:
            speed = -speed
        if speed >= 0:
            GPIO.output(in1, GPIO.HIGH)
            GPIO.output(in2, GPIO.LOW)
            pwm.ChangeDutyCycle(abs(speed))
        else:
            GPIO.output(in1, GPIO.LOW)
            GPIO.output(in2, GPIO.HIGH)
            pwm.ChangeDutyCycle(abs(speed))

    def drive(self, left: float, right: float) -> None:
        left = clamp(left, -100, 100)
        right = clamp(right, -100, 100)
        if self.cfg.SWAP_WHEELS:
            left, right = right, left
        if self.dry:
            print(f"[MOTOR] L={left:.1f} R={right:.1f}")
            return
        self._set_motor(self.pwm_left, self.cfg.LEFT_IN1, self.cfg.LEFT_IN2, left, self.cfg.INVERT_LEFT)
        self._set_motor(self.pwm_right, self.cfg.RIGHT_IN1, self.cfg.RIGHT_IN2, right, self.cfg.INVERT_RIGHT)

    def stop(self) -> None:
        if self.dry:
            print("[MOTOR] stop")
            return
        if self.pwm_left is not None:
            self.pwm_left.ChangeDutyCycle(0)
        if self.pwm_right is not None:
            self.pwm_right.ChangeDutyCycle(0)

    def cleanup(self) -> None:
        self.stop()
        if not self.dry:
            if self.pwm_left is not None:
                self.pwm_left.stop()
            if self.pwm_right is not None:
                self.pwm_right.stop()
            GPIO.cleanup()


# =============================================================================
# 霍尔编码器（forward_pid 读速 + turn_angle 累计脉冲，互不干扰）
# =============================================================================

class WheelEncoder:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.dry = cfg.DRY_RUN or GPIO is None
        self.lcounter = 0
        self.rcounter = 0
        self.lspeed = 0.0
        self.rspeed = 0.0
        self._count_left = 0
        self._count_right = 0
        self._lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._enabled = False

    def setup(self) -> None:
        if self.dry:
            print("[ENCODER] DRY_RUN，跳过霍尔初始化")
            return
        GPIO.setup([self.cfg.LEFT_ENCODER, self.cfg.RIGHT_ENCODER], GPIO.IN)
        GPIO.add_event_detect(self.cfg.LEFT_ENCODER, GPIO.RISING, callback=self._on_left)
        GPIO.add_event_detect(self.cfg.RIGHT_ENCODER, GPIO.RISING, callback=self._on_right)
        self._enabled = True

    def _on_left(self, _channel: int) -> None:
        self.lcounter += 1
        with self._lock:
            self._count_left += 1

    def _on_right(self, _channel: int) -> None:
        self.rcounter += 1
        with self._lock:
            self._count_right += 1

    def reset(self) -> None:
        with self._lock:
            self._count_left = 0
            self._count_right = 0

    def read(self) -> Tuple[int, int]:
        with self._lock:
            return self._count_left, self._count_right

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        while self.running:
            self.lspeed = self.lcounter / self.cfg.ENCODER_PULSES_PER_REV
            self.rspeed = self.rcounter / self.cfg.ENCODER_PULSES_PER_REV
            self.lcounter = 0
            self.rcounter = 0
            time.sleep(self.cfg.FORWARD_PID_INTERVAL)

    def get_speeds(self) -> Tuple[float, float]:
        return self.lspeed, self.rspeed

    def stop(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
        if self._enabled and not self.dry:
            try:
                GPIO.remove_event_detect(self.cfg.LEFT_ENCODER)
                GPIO.remove_event_detect(self.cfg.RIGHT_ENCODER)
            except Exception:
                pass
            self._enabled = False


def _wheel_counts() -> Tuple[int, int]:
    """与 Car.drive(left, right) 一致的软件左右累计脉冲。"""
    if _encoder is None:
        return 0, 0
    pl, pr = _encoder.read()
    if CFG.ENC_SWAP:
        return pr, pl
    return pl, pr


def _pulses_for_turn(angle_deg: float) -> float:
    wheel_circ = math.pi * CFG.WHEEL_DIAMETER_CM
    turn_circ = math.pi * CFG.TRACK_WIDTH_CM
    wheel_travel = turn_circ * (abs(angle_deg) / 360.0)
    revs = wheel_travel / wheel_circ
    return revs * CFG.ENCODER_PULSES_PER_REV * CFG.TURN_CALIB


def _run_turn_to_target(
    target_pulses: float,
    base_left: float,
    base_right: float,
    step: float,
    label: str,
    *,
    dry_angle_deg: Optional[float] = None,
) -> None:
    """turn_angle 内部：编码器脉冲闭环转到目标。"""
    _, _, car = _require_ready()
    target = max(0.0, float(target_pulses))
    step = max(0.0, float(step))
    finish = CFG.ENC_FINISH_PULSES
    interval = max(0.002, CFG.ENC_LOOP_INTERVAL)

    print(f"[ENC] {label}: target={target:.0f} pulses, step={step}")

    if _encoder is None or _encoder.dry:
        if dry_angle_deg is not None:
            duration = max(0.05, abs(dry_angle_deg) / CFG.ENC_DRY_TURN_DEG_PER_SEC)
        else:
            duration = max(0.1, target / CFG.ENCODER_PULSES_PER_REV * 0.5)
        print(f"[ENC] dry run {label}: {duration:.2f}s")
        car.drive(base_left, base_right)
        time.sleep(duration)
        car.stop()
        time.sleep(0.06)
        return

    _encoder.reset()
    left = float(base_left)
    right = float(base_right)
    t0 = now()

    while True:
        if now() - t0 > CFG.ENC_TIMEOUT_S:
            print(f"[ENC] {label} timeout, stop early")
            break

        cl, cr = _wheel_counts()
        done_l = cl >= target - finish
        done_r = cr >= target - finish
        if done_l and done_r:
            break

        if cl > cr:
            left -= step
            right += step
        elif cl < cr:
            left += step
            right -= step

        if done_l:
            left = 0.0
        if done_r:
            right = 0.0

        car.drive(clamp(left, -100, 100), clamp(right, -100, 100))
        time.sleep(interval)

    car.stop()
    cl, cr = _wheel_counts()
    print(f"[ENC] {label} done: L={cl} R={cr} dt={now() - t0:.2f}s")
    time.sleep(0.06)


# =============================================================================
# 全局资源（主程序里先 setup() 再调用动作函数）
# =============================================================================

_camera: Optional[CameraThread] = None
_vision: Optional[Vision] = None
_car: Optional[Car] = None
_encoder: Optional[WheelEncoder] = None


def setup(dry_run: bool = False, show_debug: bool = True) -> None:
    """主程序开头调用一次：初始化 GPIO、霍尔编码器、摄像头线程。"""
    global _camera, _vision, _car, _encoder
    CFG.DRY_RUN = dry_run
    CFG.SHOW_DEBUG = show_debug
    _vision = Vision(CFG)
    _car = Car(CFG)
    _encoder = WheelEncoder(CFG)
    _camera = CameraThread(CFG)
    _car.setup()
    _encoder.setup()
    _encoder.start()
    _camera.start()
    time.sleep(0.2)


def cleanup() -> None:
    """主程序结束（或异常）时调用：停车、释放摄像头与 GPIO。"""
    global _camera, _car, _encoder
    if _encoder is not None:
        _encoder.stop()
        _encoder = None
    if _car is not None:
        _car.cleanup()
    if _camera is not None:
        _camera.stop()
    cv2.destroyAllWindows()


def _require_ready() -> Tuple[CameraThread, Vision, Car]:
    if _camera is None or _vision is None or _car is None:
        raise RuntimeError("请先调用 setup() 再使用 search_color / approach_target 等函数")
    return _camera, _vision, _car


def show_debug(state: str, det: Optional[Dict] = None) -> None:
    """
    调试画面：与 reference_pj/main.py 相同，使用 cv2.imshow。
    在循环里每个控制周期调用一次即可刷新窗口；按 Config.SHOW_DEBUG 开关。
    """
    if not CFG.SHOW_DEBUG:
        return
    cam, vis, _ = _require_ready()
    frame = cam.get_frame()
    if frame is None:
        return
    out = vis.draw(frame, det, state)
    cv2.imshow(CFG.DEBUG_WINDOW, out)
    cv2.waitKey(1)


def _drive_for(duration: float, left: float, right: float) -> None:
    _, _, car = _require_ready()
    car.drive(left, right)
    time.sleep(duration)
    car.stop()
    time.sleep(0.06)


# =============================================================================
# 视觉闭环动作函数
# =============================================================================

# 与 approach_target 中 vis.detect(frame, color, 1) 判定标准一致
_APPROACH_DETECT_MIN_PIXELS = 1


def search_color(
    right_pwm: float,
    interval: float,
    color: str,
) -> bool:
    """
    右轮单轮步进旋转搜索指定颜色；找到与否与 approach_target 能否开进同一标准。

    每步流程：左轮 0、右轮 right_pwm 转 interval 秒 → 停车 → 等画面稳 → 识别一帧。
    识别条件同 approach_target：最大色块面积在 [1, MAX_VALID_AREA] 内即视为找到。

    参数：
        right_pwm: 右轮 PWM（-100~100，可正可负），左轮恒为 0
        interval:  每步右轮旋转时长（秒）
        color:     blue / yellow / red（或 蓝/黄/红）

    返回：
        True  — 画面内已有可 approach 的色块，可接 approach_target(...)
        False — 在 SEARCH_FULL_ROTATION_TIME 内未找到

    示例：
        if search_color(25, 0.12, "blue"):
            approach_target("blue", 28, pid_approach, CFG.APPROACH_STOP_PIXELS)
    """
    cam, vis, car = _require_ready()
    color = _norm_color(color)
    right_pwm = clamp(float(right_pwm), -100, 100)
    interval = max(0.02, float(interval))

    print(
        f"[search_color] 找 {color}, right_pwm={right_pwm}, "
        f"interval={interval}s, timeout={CFG.SEARCH_FULL_ROTATION_TIME}s"
    )

    def try_detect() -> Optional[Dict]:
        frame = cam.get_frame()
        if frame is None:
            return None
        det = vis.detect(frame, color, _APPROACH_DETECT_MIN_PIXELS)
        show_debug(f"search_color {color}", det)
        return det

    t0 = now()

    det = try_detect()
    if det is not None:
        car.stop()
        print(f"[search_color] 已发现 {color}, px={det['pixel_count']}")
        return True

    while now() - t0 < CFG.SEARCH_FULL_ROTATION_TIME:
        car.drive(0, right_pwm)
        time.sleep(interval)
        car.stop()
        time.sleep(CFG.SEARCH_COLOR_SETTLE_TIME)

        det = try_detect()
        if det is not None:
            print(f"[search_color] 已发现 {color}, px={det['pixel_count']}")
            return True

    car.stop()
    print(f"[search_color] 超时未找到 {color}")
    return False


def approach_target(
    color: str,
    forward_speed: float,
    pid_params: PidInput,
    stop_pixels: int,
) -> bool:
    """
    使用 PID 直行靠近指定颜色魔方，色块像素数达到 stop_pixels 后停止。

    参数：
        color: blue / yellow / red
        forward_speed: 前进基础 PWM 占空比（左右轮同向）
        pid_params: PidParams 或 (kp, ki, kd)
        stop_pixels: 达到该像素面积（轮廓面积）后结束前进

    返回：
        True  — 已靠近到阈值
        False — 超时或长时间丢失目标
    """
    cam, vis, car = _require_ready()
    color = _norm_color(color)
    pp = _parse_pid(pid_params)
    pid = PID(pp.kp, pp.ki, pp.kd)
    pid.reset()

    print(f"[approach_target] 靠近 {color}, speed={forward_speed}, stop>={stop_pixels}")

    lost = 0
    t0 = now()

    while now() - t0 < CFG.APPROACH_TIMEOUT:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.02)
            continue

        det = vis.detect(frame, color, 1)
        show_debug(f"approach {color}", det)

        if det is None:
            lost += 1
            if lost < CFG.APPROACH_LOST_BACKUP_FRAMES:
                car.drive(-forward_speed * 0.5, -forward_speed * 0.5)
                time.sleep(0.04)
                continue
            car.stop()
            print(f"[approach_target] 丢失 {color} 过久")
            return False

        lost = 0
        if det["pixel_count"] >= stop_pixels:
            car.stop()
            print(f"[approach_target] 到达 stop_pixels={det['pixel_count']}")
            time.sleep(0.1)
            return True

        error = det["center_x"] - CFG.WIDTH / 2.0
        delta = pid.feedback(error)
        delta = clamp(delta, -pp.max_delta, pp.max_delta)
        if abs(delta) < pp.min_delta:
            delta = 0.0

        # error>0 目标偏右 -> 左轮快、右轮慢
        left = forward_speed + delta
        right = forward_speed - delta
        car.drive(left, right)
        time.sleep(0.02)

    car.stop()
    print("[approach_target] 超时")
    return False


def turn_angle(angle_deg: float, speed: float = 50, step: float = 0.2) -> None:
    """
    编码器闭环原地转指定角度（v4+ 新增，setup 后直接调用）。

    参数：
        angle_deg: 角度（度）。正=左转，负=右转
        speed:     轮速 PWM 幅度，默认 50
        step:      左右同步修正步长，默认 0.2

    示例（复制即用）：
        turn_angle(90)     # 左转 90°
        turn_angle(-90)    # 右转 90°
        turn_angle(45, 45) # 左转 45°，稍慢
    """
    angle_deg = float(angle_deg)
    s = clamp(abs(float(speed)), 0, 100)
    target = _pulses_for_turn(angle_deg)
    if angle_deg >= 0:
        _run_turn_to_target(
            target, -s, s, step, f"turnL {angle_deg:.0f}deg", dry_angle_deg=angle_deg
        )
    else:
        _run_turn_to_target(
            target, s, -s, step, f"turnR {-angle_deg:.0f}deg", dry_angle_deg=angle_deg
        )


def turn_left(duration: float, wheel_speed: float) -> None:
    """
    逆时针原地旋转（左转），持续 duration 秒（开环，与 turn_angle 二选一）。

    参数：
        duration: 执行时长（秒）
        wheel_speed: 左右轮 PWM 占空比大小（左负右正）
    """
    print(f"[turn_left] {duration:.2f}s speed={wheel_speed}")
    _drive_for(duration, -abs(wheel_speed), abs(wheel_speed))


def turn_right(duration: float, wheel_speed: float) -> None:
    """
    顺时针原地旋转（右转），持续 duration 秒。

    参数：
        duration: 执行时长（秒）
        wheel_speed: 左右轮 PWM 占空比大小（左正右负）
    """
    print(f"[turn_right] {duration:.2f}s speed={wheel_speed}")
    _drive_for(duration, abs(wheel_speed), -abs(wheel_speed))


def forward_time(left_speed: float, right_speed: float, duration: float) -> None:
    """
    按给定左右轮 PWM 占空比行驶一段时间（前进或后退均可）。

    参数：
        left_speed:  左轮占空比，-100~100；正值前进，负值反转
        right_speed: 右轮占空比，-100~100；正值前进，负值反转
        duration:    执行时长（秒），始终为正

    示例：
        forward_time(30, 30, 1.0)    # 直行前进
        forward_time(-25, -25, 0.8)  # 直行后退
        forward_time(20, -20, 0.5)   # 原地旋转（一正一负）
    """
    left_speed = clamp(float(left_speed), -100, 100)
    right_speed = clamp(float(right_speed), -100, 100)
    duration = max(0.0, float(duration))
    print(f"[forward_time] {duration:.2f}s L={left_speed} R={right_speed}")
    _drive_for(duration, left_speed, right_speed)


def forward_pid(
    left_speed: float,
    right_speed: float,
    step: float,
    interval: float,
    duration: float,
) -> None:
    """
    霍尔编码器闭环直行（参考 auto_back.py）：
    以左右轮初速度前进，每隔 interval 读编码器转速并修正，左快则左减右加，右快则右减左加。

    参数：
        left_speed:  左轮初始 PWM 占空比（可负表示后退）
        right_speed: 右轮初始 PWM 占空比
        step:        每次调整的速度修正步长（auto_back 默认 0.2）
        interval:    调整间隔（秒），每隔多久读编码器并修正一次（auto_back 默认 0.01）
        duration:    前进总时长（秒）

    用法（setup 后可直接调用，与 forward_time 一样即插即用）：
        forward_pid(20, 20, 0.2, 0.01, 1.6)
    """
    _, _, car = _require_ready()
    left = float(left_speed)
    right = float(right_speed)
    interval = max(0.005, float(interval))

    print(
        f"[forward_pid] {duration:.2f}s L0={left} R0={right} "
        f"step={step} interval={interval}s"
    )

    t0 = now()
    while now() - t0 < duration:
        car.drive(left, right)
        time.sleep(interval)

        if _encoder is not None and not _encoder.dry:
            lspeed, rspeed = _encoder.get_speeds()
            if lspeed > rspeed:
                right += step
                left -= step
            elif lspeed < rspeed:
                right -= step
                left += step

        left = clamp(left, -100, 100)
        right = clamp(right, -100, 100)

    car.stop()
    time.sleep(0.06)
    print(f"[forward_pid] done L={left:.1f} R={right:.1f}")


if __name__ == "__main__":
    # ----- 1. 初始化（调试可先 DRY_RUN=True 只看识别）-----
    setup(dry_run=False, show_debug=True)

    pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

    try:
        # turn_angle 即插即用示例（可把 turn_left 换成 turn_angle(90)）
        # turn_angle(90)
        # time.sleep(0.5)

        #find blue and turn left
        time.sleep(0.5)
        #approach_target("blue", forward_speed=34, pid_params=pid_approach, stop_pixels=8000)
        #time.sleep(0.3)
        turn_angle(45)# delete or shorter, depends on where to place the car
        
        time.sleep(0.3)
        forward_pid(40,40,0.5,0.05,1.0)
        time.sleep(0.3)
        search_color(-40,0.3,"yellow")
        #find yellow and turn right
        approach_target("yellow", forward_speed=28, pid_params=pid_approach, stop_pixels=15000)
        time.sleep(0.3)
        turn_angle(-60)
        time.sleep(0.3)
        forward_pid(40,40,0.5,0.05,0.8)
        time.sleep(0.3)
        turn_angle(60)
        time.sleep(0.3)
        search_color(40,0.3,"red")
        #find red and turn left
        approach_target("red", forward_speed=28, pid_params=pid_approach, stop_pixels=6000)
        time.sleep(0.3)
        turn_angle(150)
        time.sleep(0.3)
        search_color(40,0.2,"yellow")
        approach_target("yellow", forward_speed=28, pid_params=pid_approach, stop_pixels=8000)
        time.sleep(0.3)
        turn_angle(-90)
        time.sleep(0.3)
        forward_pid(40,40,0.5,0.05,1.0)
        time.sleep(0.3)
        turn_angle(90)
        time.sleep(0.3)
        forward_pid(40,40,0.5,0.05,0.8)
        time.sleep(0.3)
        
        search_color(40,0.2,"blue")
        
        #find blue and turn left
        approach_target("blue", forward_speed=28, pid_params=pid_approach, stop_pixels=6000)
        time.sleep(0.3)
        turn_angle(90)
        time.sleep(0.3)
        forward_pid(40,40,0.5,0.01,0.8)
        time.sleep(0.3)
        turn_angle(30)
        time.sleep(0.3)
        search_color(40,0.2,"red")
        
        #find red and sprint to the finish line
        approach_target("red", forward_speed=28, pid_params=pid_approach, stop_pixels=15000)
        time.sleep(0.3)
        '''
        turn_right(0.2,60)
        time.sleep(0.5)
        forward_pid(40,40,0.5,0.01,0.8)
        time.sleep(0.5)
        turn_left(0.2,60)
        time.sleep(0.5)
        forward_pid(40,40,0.5,0.05,3)
        '''
        cleanup()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()