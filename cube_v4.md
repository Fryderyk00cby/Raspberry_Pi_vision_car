# cube_v4.py 使用说明

魔方绕桩任务的**可拼接函数库**。本文件不提供固定比赛流程，只提供「初始化 → 视觉/运动函数 → 清理」积木块，由你在 `main` 里按顺序拼接。

依赖：OpenCV、NumPy、树莓派上的 RPi.GPIO（非树莓派环境会自动进入 DRY_RUN，只打印电机指令）。

> v5 增强版（左/右轮搜色、减速靠近、丢目标恢复等）见 **[cube_v5.md](./cube_v5.md)**。

---

## 目录

- [1. 基本用法模板](#1-基本用法模板)
- [2. 速度参数约定](#2-速度参数约定)
- [3. 传参 vs Config：改哪里？](#3-传参-vs-config改哪里)
- [4. Config 总表](#4-config-总表按用途分类)
- [5. PidParams（PID 参数）](#5-pid-参数-pidparams传给-approach_target不算-config)
- [6. 生命周期 API](#6-生命周期-api)
- [7. search_color](#7-search_colorright_pwm-interval-color--bool)
- [8. approach_target](#8-approach_targetcolor-forward_speed-pid_params-stop_pixels--bool)
- [9. 开环 / 编码器运动 API](#9-开环--编码器运动-api)
- [10. 函数一览](#10-函数一览)
- [11. 典型比赛流程](#11-典型比赛流程参考-__main__)
- [12. 临场标定清单](#12-临场标定清单)
- [13. 调试画面](#13-调试画面)
- [14. 常见问题](#14-常见问题)

---

## 1. 基本用法模板

所有动作函数都必须在 `setup()` 之后、`cleanup()` 之前调用。

```python
from cube_v4 import setup, cleanup, search_color, approach_target, turn_left, forward_pid, PidParams, CFG

setup(dry_run=False, show_debug=True)

pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

try:
    if search_color(-40, 0.3, "blue"):
        approach_target("blue", 28, pid_approach, stop_pixels=15000)
    turn_left(0.2, 60)
    forward_pid(40, 40, 0.5, 0.05, 0.8)
except KeyboardInterrupt:
    pass
finally:
    cleanup()
```

| 步骤 | 函数 | 说明 |
|------|------|------|
| 开头 | `setup()` | 初始化 GPIO、霍尔编码器、摄像头线程 |
| 中间 | 各种动作函数 | 见下文 |
| 结尾 | `cleanup()` | 停车、释放摄像头与 GPIO，务必放在 `finally` 里 |

**调试模式：**

- `setup(dry_run=True)`：不驱动电机，只打印 `[MOTOR]` 日志，适合在电脑上测识别逻辑。
- `setup(show_debug=False)`：关闭 `cv2.imshow` 调试窗口。

---

## 2. 速度参数约定

所有速度均为 **PWM 占空比**，范围 **-100 ~ 100**：

| 符号 | 含义 |
|------|------|
| 正值 | 该轮前进 |
| 负值 | 该轮反转（后退） |
| 左负右正 | 逆时针原地转（`turn_left`） |
| 左正右负 | 顺时针原地转（`turn_right`） |

若左右轮装反或方向反了，改 `Config` 里的 `SWAP_WHEELS`、`INVERT_LEFT`、`INVERT_RIGHT`。

---

## 3. 传参 vs Config：改哪里？

| 类型 | 在哪里改 | 什么时候改 | 示例 |
|------|----------|------------|------|
| **传参** | 调用函数时写在 `main` 里 | **每个赛段、每次动作**都可能不同 | `stop_pixels=15000`、`forward_pid(..., 0.8)` |
| **PidParams** | `main` 里构造 `PidParams(...)` | 靠近抖动/响应慢时调 | `kp=0.18, min_delta=8` |
| **Config (`CFG`)** | `cube_v4.py` 顶部 `Config` 或运行时 `CFG.xxx = ...` | **接线、HSV、分辨率、超时**等现场一次标定 | `LOW_BLUE`、`SEARCH_COLOR_SETTLE_TIME` |

**经验法则：**

- 和「这一趟走多远、转多久、停多近」相关的 → **传参**
- 和「硬件接线、摄像头、颜色识别、电机方向、全局超时」相关的 → **Config**
- 和「PID 手感」相关的 → **PidParams**（也算传参，但单独成组）

下文每个 API 都会拆成 **传参** 与 **Config** 两表。

---

## 4. Config 总表（按用途分类）

全局对象：`from cube_v4 import CFG` 或改 `cube_v4.py` 里 `Config` 默认值。

### 4.1 硬件 / 接线（装好车后改一次）

| 字段 | 默认 | 关联 API | 说明 |
|------|------|----------|------|
| `LEFT_PWM` / `RIGHT_PWM` 等 GPIO | 见代码 | 全部电机函数 | 电机接线，错则全车方向乱 |
| `PWM_FREQ` | 80 | 全部电机 | PWM 频率 |
| `LEFT_ENCODER` / `RIGHT_ENCODER` | 6 / 12 | `forward_pid`, `turn_angle` | 霍尔引脚 |
| `ENCODER_PULSES_PER_REV` | 585 | `forward_pid` | 课件给定，一般不改 |
| `SWAP_WHEELS` | False | 全部 `drive` | 左右命令对调 |
| `INVERT_LEFT` / `INVERT_RIGHT` | False | 全部 `drive` | 单侧电机正反转对调 |

### 4.2 摄像头（影响帧率与识别稳定性）

| 字段 | 默认 | 关联 API | 说明 |
|------|------|----------|------|
| `CAMERA_ID` | 0 | 全部视觉 | `/dev/video0` 等 |
| `CAMERA_BACKEND` | v4l2 | 全部视觉 | 树莓派建议 v4l2 |
| `WIDTH` / `HEIGHT` | 320 / 240 | 全部视觉 | 降分辨率换帧率；**改后须重标 px 阈值** |
| `FPS` | 40 | 全部视觉 | 目标帧率 |
| `SHOW_DEBUG` / `DEBUG_WINDOW` | True / cube debug | `show_debug` | 也可 `setup(show_debug=False)` |

### 4.3 HSV 颜色（影响搜色/靠近能否看到色块）

| 字段 | 关联 API |
|------|----------|
| `LOW_RED1` / `HIGH_RED1` / `LOW_RED2` / `HIGH_RED2` | `search_color`, `approach_target` |
| `LOW_YELLOW` / `HIGH_YELLOW` | 同上 |
| `LOW_BLUE` / `HIGH_BLUE` | 同上 |

用 `HSV_test.py` 标定后写入 Config。

### 4.4 视觉面积 / 超时（不常改，除非换分辨率或行为异常）

| 字段 | 默认 | 关联 API | 说明 |
|------|------|----------|------|
| `MAX_VALID_AREA` | 80000 | `search_color`, `approach_target` | 轮廓过大当误检；换分辨率须缩放 |
| `APPROACH_STOP_PIXELS` | 21000 | 文档参考值 | **实际停靠多用传参 `stop_pixels`** |
| `SEARCH_FULL_ROTATION_TIME` | 10 s | `search_color` | 搜色总超时 |
| `SEARCH_COLOR_SETTLE_TIME` | 0.3 s | `search_color` | 每步停车后等画面稳 |
| `APPROACH_TIMEOUT` | 15 s | `approach_target` | 靠近单段最长时间 |
| `APPROACH_LOST_BACKUP_FRAMES` | 10 | `approach_target` | 丢目标后倒车 retry 帧数 |
| `APPROACH_MIN_DELTA` / `APPROACH_MAX_DELTA` | 6 / 18 | 未直接使用 | 请用 `PidParams` 里的同名项 |

640×480 → 320×240 时轮廓面积约 ×0.25。

### 4.5 turn_angle 角度闭环（v4+ 新增）

| 字段 | 默认 | 关联 API | 说明 |
|------|------|----------|------|
| `WHEEL_DIAMETER_CM` | 6.5 | `turn_angle` | 车轮直径（cm） |
| `TRACK_WIDTH_CM` | 14.0 | `turn_angle` | 两轮中心距（cm） |
| `TURN_CALIB` | 0.5 | `turn_angle` | 角度修正：转不够加大，转过头减小 |
| `ENC_FINISH_PULSES` | 4 | `turn_angle` | 提前停脉冲，吃惯性 |
| `ENC_TIMEOUT_S` | 6.0 | `turn_angle` | 超时保护（打滑/卡死） |
| `ENC_LOOP_INTERVAL` | 0.01 | `turn_angle` | 闭环控制周期 |
| `ENC_SWAP` | False | `turn_angle` | 编码器左右对调 |
| `ENC_DRY_TURN_DEG_PER_SEC` | 90.0 | `turn_angle` | DRY_RUN 下角速度估算 |

---

## 5. PID 参数 PidParams（传给 approach_target，不算 Config）

`approach_target` 接受 `PidParams` 或元组 `(kp, ki, kd)`。

```python
from cube_v4 import PidParams

pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)
```

| 字段 | 含义 |
|------|------|
| `kp, ki, kd` | 标准 PID 系数 |
| `min_delta` | 输出小于此值时视为 0，避免抖动 |
| `max_delta` | 输出上限，限制转向幅度 |

**横向误差定义：** `error = 色块中心_x - 画面宽度/2`。error > 0 表示目标在画面右侧。

320 宽时同样物理偏差对应更少像素，`kp` 约为 640 宽时的 ~2 倍。

---

## 6. 生命周期 API

### setup(dry_run=False, show_debug=True)

**功能：** 程序入口，初始化视觉、电机、霍尔、摄像头线程。

| 类型 | 名称 | 默认 | 说明 |
|------|------|------|------|
| 传参 | `dry_run` | False | True=只打印电机，不驱动 GPIO |
| 传参 | `show_debug` | True | 是否弹 `cv2.imshow` 窗口 |
| Config | 其余 GPIO/摄像头/HSV | 见 §4 | 在 `setup` 前改 `CFG` 或源码 `Config` |

### cleanup()

**功能：** 停车、停编码器、释放摄像头与 GPIO。**无传参**，必须在 `finally` 里调用。

### show_debug(state, det=None)

**功能：** 手动刷新调试窗口；闭环函数内部已自动调用。

| 传参 | 说明 |
|------|------|
| `state` | 左上角状态文字 |
| `det` | 可选检测结果 dict |

| Config | 说明 |
|--------|------|
| `SHOW_DEBUG` | False 时即使调用也不显示 |
| `DEBUG_WINDOW` | 窗口标题 |

---

## 7. search_color(right_pwm, interval, color) → bool

**功能：** 右轮步进搜色——转一步 → 停车等待 → 识别一帧；找到则返回 True，可接 `approach_target`。

**流程：** `drive(0, right_pwm)` → `interval` 秒 → 停 → 等 `SEARCH_COLOR_SETTLE_TIME` → `detect`。

```python
search_color(-40, 0.3, "yellow")
```

### 传参（main 里常改）

| 参数 | 说明 | 典型值 / 标定 |
|------|------|----------------|
| `right_pwm` | 右轮 PWM，左轮恒为 0；正负决定扫向 | ±18~±40 |
| `interval` | 每步转动时长（秒） | 0.12~0.3 |
| `color` | 目标颜色 | `"blue"` / `"yellow"` / `"red"` |

### Config（不常改）

| 字段 | 默认 | 何时改 |
|------|------|--------|
| `SEARCH_COLOR_SETTLE_TIME` | 0.3 s | 画面糊/帧率低 → 加大；搜色太慢 → 减小 |
| `SEARCH_FULL_ROTATION_TIME` | 10 s | 全场扫不完 → 加大 |
| `MAX_VALID_AREA` | 80000 | 误检或换分辨率 |
| HSV 六项 | 见 §4.3 | 识别不到颜色 |

### 返回值

| 值 | 含义 |
|----|------|
| `True` | 检测到色块（面积 1~MAX_VALID_AREA） |
| `False` | 超时未找到 |

---

## 8. approach_target(color, forward_speed, pid_params, stop_pixels) → bool

**功能：** PID 控制左右轮差速，直行靠近色块；`pixel_count >= stop_pixels` 时停车。

```python
approach_target("blue", 28, pid_approach, stop_pixels=15000)
```

### 传参（main 里常改）

| 参数 | 说明 | 典型值 / 标定 |
|------|------|----------------|
| `color` | 要跟的颜色 | 与 `search_color` 一致 |
| `forward_speed` | 前进基础 PWM（左右同向） | 22~32；太快易晃、冲过头 |
| `pid_params` | `PidParams` 或 `(kp,ki,kd)` | 见 §5 |
| `stop_pixels` | 轮廓面积达到即停 | debug 看 `px=`，蓝/黄/红可不同 |

### Config（不常改）

| 字段 | 默认 | 何时改 |
|------|------|--------|
| `APPROACH_TIMEOUT` | 15 s | 靠近总超时 |
| `APPROACH_LOST_BACKUP_FRAMES` | 10 | 丢目标后倒车 retry 次数 |
| `MAX_VALID_AREA` | 80000 | 贴太近误检消失 |
| HSV | 见 §4.3 | 靠近时丢色 |

**PidParams 传参（和 Config 无关）：** `min_delta` / `max_delta` 在 `PidParams(...)` 里设，控制转向死区与上限。

### 丢目标行为

连续 `det is None`：先 `-forward_speed*0.5` 倒车；超过 `APPROACH_LOST_BACKUP_FRAMES` 帧 → 返回 `False`。

### 返回值

| 值 | 含义 |
|----|------|
| `True` | 到达 `stop_pixels` |
| `False` | 超时或丢失过久 |

---

## 9. 开环 / 编码器运动 API

不依赖视觉；执行完自动 `stop()`。

### turn_angle(angle_deg, speed=50, step=0.2)

**功能：** 编码器闭环原地转指定角度。正=左转，负=右转。

```python
turn_angle(90)              # 左转 90°（默认 speed=50, step=0.2）
turn_angle(-90)             # 右转 90°
turn_angle(45, 45)          # 左转 45°，稍慢
```

#### 传参（main 里常改）

| 参数 | 说明 | 典型值 |
|------|------|--------|
| `angle_deg` | 角度（度）；正左负右 | 45 / 90 / -90 |
| `speed` | 转弯 PWM 幅度（默认 50） | 40~60 |
| `step` | 左右同步修正步长（默认 0.2） | 0.2~0.5 |

#### Config（不常改）

见 §4.5（`TURN_CALIB`、轮径轮距、`ENC_*`）。

#### 推荐调参顺序（v4/v5 统一）

1. 先调 `angle_deg`（目标角度本身）
2. 再调 `step`（左右同步修正强度）
3. 最后调 `TURN_CALIB`（系统性偏差补偿）

有临时小角度微调需求时，再用 `turn_left` / `turn_right` 补一小段时间。

### turn_left(duration, wheel_speed) / turn_right(duration, wheel_speed)

**功能：** 定时原地转；**不读编码器**，角度靠标定 `duration` + `wheel_speed`。

#### 传参（main 里常改）

| 参数 | 说明 | 典型值 |
|------|------|--------|
| `duration` | 转动秒数 | 0.15~0.25 约 90°（需实测） |
| `wheel_speed` | 左右差速大小 | 40~60 |

#### Config

仅 `SWAP_WHEELS` / `INVERT_*` 影响方向；无专用转弯 Config。

---

### forward_time(left_speed, right_speed, duration)

**功能：** 定时差速行驶；可前进、后退、弧线、原地转。

#### 传参（main 里常改）

| 参数 | 说明 | 示例 |
|------|------|------|
| `left_speed` | 左轮 PWM，可负 | `50` / `-25` |
| `right_speed` | 右轮 PWM，可负 | `50` / `-25` |
| `duration` | 秒数 | `0.8` |

#### Config

`SWAP_WHEELS` / `INVERT_*`；无其它专用项。

---

### forward_pid(left_speed, right_speed, step, interval, duration)

**功能：** 按**时间**直行；每隔 `interval` 读霍尔脉冲增量，用 `step` 修正左右同步。**不按厘米停**。

```python
forward_pid(40, 40, 0.5, 0.05, 0.8)
```

#### 传参（main 里常改）

| 参数 | 说明 | 典型值 |
|------|------|--------|
| `left_speed` / `right_speed` | 初始 PWM | 常左右相同，如 40, 40 |
| `step` | 每周期修正步长 | 0.2~0.5；越大纠偏越猛 |
| `interval` | 修正周期（秒） | 0.01~0.05 |
| `duration` | 总时长（秒） | 按赛道标定 |

#### Config（不常改）

| 字段 | 默认 | 何时改 |
|------|------|--------|
| `LEFT_ENCODER` / `RIGHT_ENCODER` | 6 / 12 | 接线 |
| `ENCODER_PULSES_PER_REV` | 585 | 极少改 |
| `FORWARD_PID_INTERVAL` | 0.01 | v4 内部采样参考 |

---

## 10. 函数一览

| 函数 | 类型 | 简要说明 |
|------|------|----------|
| `setup` | 生命周期 | 初始化硬件与摄像头 |
| `cleanup` | 生命周期 | 释放资源 |
| `show_debug` | 调试 | 刷新 imshow 窗口 |
| `search_color` | 视觉闭环 | 右轮步进搜色 |
| `approach_target` | 视觉闭环 | PID 靠近色块 |
| `turn_angle` | 编码器闭环 | 按角度原地转（正左负右） |
| `turn_left` | 开环 | 逆时针转 |
| `turn_right` | 开环 | 顺时针转 |
| `forward_time` | 开环 | 定时差速 |
| `forward_pid` | 编码器闭环 | 霍尔直行 |

---

## 11. 典型比赛流程（参考 __main__）

文件末尾 `if __name__ == "__main__"` 是一段完整绕桩示例，逻辑如下：

```
靠近蓝 → turn_angle 左转 → 直行 → turn_angle 右转 → 直行 → 搜黄 → ...
→ 靠近黄 → turn_angle 右转 → 直行 → 搜红 → 靠近红 → turn_angle 左转
→ ...（按赛道继续拼接）
```

对应代码片段：

```python
setup(dry_run=False, show_debug=True)
pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

# 第一段：已知蓝块在前方，直接靠近
approach_target("blue", 34, pid_approach, stop_pixels=8000)
turn_angle(90)
forward_pid(40, 40, 0.5, 0.05, 0.6)

# 搜下一个颜色
search_color(-40, 0.3, "yellow")
approach_target("yellow", 34, pid_approach, stop_pixels=10000)
# ... 后续同理
```

你可以复制 `__main__` 为起点，只改时间、速度、`stop_pixels` 和顺序。

---

## 12. 临场标定清单

| 标定项 | 怎么标 | 传参 or Config |
|--------|--------|----------------|
| HSV 颜色 | `HSV_test.py` | **Config** `LOW_*` / `HIGH_*` |
| 搜色步进 | 每步扫到新区域 | **传参** `right_pwm`、`interval` |
| 搜色停车等待 | 画面稳不稳 | **Config** `SEARCH_COLOR_SETTLE_TIME`（默认 0.3） |
| 搜色总超时 | 能否扫完一圈 | **Config** `SEARCH_FULL_ROTATION_TIME` |
| 靠近停止距离 | debug 看 `px=` | **传参** `stop_pixels` |
| PID 手感 | 抖/慢/冲 | **传参** `PidParams` |
| 转弯角度（闭环） | `turn_angle(90)` 量角度 | **传参** `angle_deg`；**Config** `TURN_CALIB` |
| 转弯角度（开环） | 量 90° 对应时间 | **传参** `turn_left`/`turn_right` |
| 直行距离 | 量赛道长度 | **传参** `forward_pid` 的 `duration` |
| 直行走直 | 长距离跑偏 | **传参** `forward_pid` 的 `step` |
| 编码器左右反 | 左右角度方向怪 | **Config** `ENC_SWAP` |
| 电机方向 | 前进变后退 | **Config** `SWAP_WHEELS` / `INVERT_*` |

---

## 13. 调试画面

`SHOW_DEBUG=True` 时，窗口显示：

- 画面竖直中心线（对准参考）
- 色块矩形框、中心点
- `px=` 轮廓面积（标定 `stop_pixels` 用）
- 当前状态文字（如 `approach blue`）

远程查看：VNC 连树莓派，或 SSH -X 转发 X11。

---

## 14. 常见问题

**Q: 提示「请先调用 setup()」**  
A: 在调用任何动作函数前先 `setup()`。

**Q: 识别不到颜色**  
A: 先跑 `HSV_test.py` 标定 HSV；检查光照、摄像头是否脏。

**Q: search_color 找到了但 approach 立刻丢**  
A: 可能 stop_pixels 过大/过小，或 forward_speed 太快；降低速度或调整阈值。

**Q: 车走不直**  
A: 短距离用 `forward_time`；长距离用 `forward_pid` 并标定 `step`。

**Q: turn_angle 转角不准**  
A: 推荐顺序：先调 `angle_deg`，再调 `step`，最后调 `TURN_CALIB`。若左右对不上，先试 `ENC_SWAP`；再检查 `WHEEL_DIAMETER_CM` / `TRACK_WIDTH_CM`。

**Q: 在 Windows 上 import 报错 GPIO**  
A: 正常，会自动 DRY_RUN；要测识别请 `setup(dry_run=True)` 并接摄像头。
