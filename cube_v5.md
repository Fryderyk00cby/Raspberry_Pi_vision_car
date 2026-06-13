# cube_v5.py 使用说明

魔方绕桩任务的**可拼接函数库（v5 增强版）**。在 `cube_v4.py` 全部能力之上，新增左/右轮搜色、减速靠近、丢目标自动恢复、`turn_angle` 编码器按角度转弯。

依赖：OpenCV、NumPy、树莓派上的 RPi.GPIO（非树莓派环境会自动进入 DRY_RUN，只打印电机指令）。

> **v4 共有 API**（`setup`、`forward_time`、`PidParams、Config 总表` 等）的完整传参/Config 说明见 **[cube_v4.md](./cube_v4.md)**。本文档对 **v5 全部公开 API** 做同样粒度的说明，并补充 v5 专有 Config。

---

## 目录

- [1. v5 相对 v4 的变更摘要](#1-v5-相对-v4-的变更摘要)
- [2. 传参 vs Config：改哪里？](#2-传参-vs-config改哪里)
- [3. v5 专有 Config（编码器角度）](#3-v5-专有-config编码器角度)
- [4. 基本用法模板](#4-基本用法模板)
- [5. 生命周期 API](#5-生命周期-api)
- [6. search_color](#6-search_colorwheel_pwm-interval-color-use_left_wheelfalse--bool)
- [7. approach_target](#7-approach_targetcolor-forward_speed-pid_params-stop_pixels--bool)
- [8. approach_target_brake](#8-approach_target_brake--bool-v5-新增)
- [9. approach_target_recover](#9-approach_target_recover--bool-v5-新增)
- [10. turn_angle](#10-turn_angleangle_deg-speed-step-v5-新增)
- [11. 开环 / 按时间编码器 API](#11-开环--按时间编码器-api与-v4-相同)
- [12. 函数一览](#12-函数一览)
- [13. 典型比赛流程](#13-典型比赛流程参考-__main__)
- [14. v5 临场标定清单](#14-v5-临场标定清单)
- [15. 常见问题](#15-常见问题v5-补充)

---

## 1. v5 相对 v4 的变更摘要

| 项目 | v4 | v5 |
|------|----|----|
| `search_color` 驱动轮 | 仅右轮（参数名 `right_pwm`） | 默认右轮；可选左轮（`use_left_wheel=True`） |
| 减速靠近 | 无 | `approach_target_brake` |
| 丢目标恢复 | 无 | `approach_target_recover` |
| 按角度转弯 | 无（仅开环 `turn_left`） | `turn_angle`（编码器脉冲闭环） |
| 编码器模式 | 后台读速线程 | GPIO 回调累计脉冲（无后台线程） |

直行仍用 v4 的 `forward_pid`（按时间）。

---

## 2. 传参 vs Config：改哪里？

与 v4 相同，见 [cube_v4.md §3](./cube_v4.md#3-传参-vs-config改哪里)。

| 类型 | 在哪里改 | 什么时候改 |
|------|----------|------------|
| **传参** | `main` 里调用函数时 | 每个赛段：角度、速度、停多近 |
| **PidParams** | `PidParams(kp=..., min_delta=...)` | 靠近 PID 手感 |
| **Config (`CFG`)** | 源码 `Config` 或 `CFG.xxx = ...` | 接线、HSV、轮径/轮距、CALIB、超时 |

**v5 额外规则：**

- `turn_angle` 的**目标角度** → **传参**；**轮径、轮距、CALIB、提前停脉冲** → **Config**
- `approach_target_recover` 里恢复用的后退/搜色参数 → **传参**（有默认值，可按赛段改）

---

## 3. v5 专有 Config（编码器角度）

v4 Config 见 [cube_v4.md §4](./cube_v4.md#4-config-总表按用途分类)。下表为 **v5 新增或行为变更** 的字段。

| 字段 | 默认 | 关联 API | 说明 | 何时改 |
|------|------|----------|------|--------|
| `WHEEL_DIAMETER_CM` | 6.5 | `turn_angle` | 车轮直径（cm），用于角度↔脉冲换算 | 换轮胎 |
| `TRACK_WIDTH_CM` | 14.0 | `turn_angle` | 两轮中心距（cm） | 量车体 |
| `TURN_CALIB` | 0.9 | `turn_angle` | 角度修正：转不够**加大**（打滑常见） | 标定转弯 |
| `ENC_FINISH_PULSES` | 4 | `turn_angle` | 提前停脉冲，吃惯性 | 停点过冲 |
| `ENC_TIMEOUT_S` | 6.0 | `turn_angle` | 单动作超时（打滑/卡死） | 动作完不成 |
| `ENC_LOOP_INTERVAL` | 0.01 | `turn_angle` | 闭环控制周期（秒） | 极少改 |
| `ENC_SWAP` | False | 编码器读数左右对调 | 与 `SWAP_WHEELS` 不一致时试 True | 脉冲左右反 |

直行跑偏优先调 `forward_pid` 的 **`step` 传参**；转弯跑偏调 `turn_angle` 的 **`step`** 或 **`TURN_CALIB`**。

---

## 4. 基本用法模板

```python
from cube_v5 import (
    setup, cleanup,
    search_color, approach_target, approach_target_recover,
    turn_angle, forward_pid, PidParams,
)

setup(dry_run=False, show_debug=True)
pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

try:
    approach_target_recover("blue", 28, pid_approach, stop_pixels=15000)
    turn_angle(90, 50, 0.2)
    forward_pid(40, 40, 0.5, 0.05, 0.8)
except KeyboardInterrupt:
    pass
finally:
    cleanup()
```

---

## 5. 生命周期 API

与 v4 相同，详见 [cube_v4.md §6](./cube_v4.md#6-生命周期-api)。

| API | 传参 | Config |
|-----|------|--------|
| `setup(dry_run, show_debug)` | `dry_run`, `show_debug` | 其余均在 `CFG` |
| `cleanup()` | 无 | 无 |
| `show_debug(state, det)` | `state`, `det` | `SHOW_DEBUG`, `DEBUG_WINDOW` |

**v5 差异：** `setup` 不再启动编码器后台线程；霍尔仅在 GPIO 回调里累计脉冲。

---

## 6. search_color(wheel_pwm, interval, color, use_left_wheel=False) → bool

**功能：** 单轮步进搜色。固定一侧轮为 0，驱动轮转 `interval` 秒 → 停车 → 等 `SEARCH_COLOR_SETTLE_TIME` → 识别。

```python
search_color(40, 0.3, "blue")                           # 右轮（默认）
search_color(-40, 0.3, "yellow", use_left_wheel=True)   # 左轮
```

### 传参（main 里常改）

| 参数 | 说明 | 典型值 |
|------|------|--------|
| `wheel_pwm` | 驱动轮 PWM（-100~100）；另一侧恒 0 | ±18~±40 |
| `interval` | 每步转动秒数 | 0.12~0.3 |
| `color` | 目标色 | blue / yellow / red |
| `use_left_wheel` | False=右轮驱动；True=左轮驱动 | 扫不到时切换 |

### Config（不常改）

| 字段 | 默认 | 何时改 |
|------|------|--------|
| `SEARCH_COLOR_SETTLE_TIME` | 0.5 s | 画面糊 → 加大 |
| `SEARCH_FULL_ROTATION_TIME` | 10 s | 扫不完 → 加大 |
| `MAX_VALID_AREA` + HSV | 见 v4 §4 | 误检 / 认不出色 |

### 返回值

| 值 | 含义 |
|----|------|
| `True` | 找到色块，可 `approach_target` |
| `False` | 超时未找到 |

**v4 迁移：** 第一个参数名 `right_pwm` → `wheel_pwm`，位置不变；`search_color(-40, 0.3, "yellow")` 无需改。

---

## 7. approach_target(color, forward_speed, pid_params, stop_pixels) → bool

与 v4 完全相同。详见 [cube_v4.md §8](./cube_v4.md#8-approach_targetcolor-forward_speed-pid_params-stop_pixels--bool)。

| 传参（常改） | Config（不常改） |
|--------------|------------------|
| `color`, `forward_speed`, `pid_params`, `stop_pixels` | `APPROACH_TIMEOUT`, `APPROACH_LOST_BACKUP_FRAMES`, HSV, `MAX_VALID_AREA` |

---

## 8. approach_target_brake(...) → bool 【v5 新增】

**功能：** 两段速度靠近。面积 ≥ `brake_pixel` 后从 `forward_speed` 降到 `brake_speed`，到 `stop_pixels` 停车。防止冲过头。

```python
approach_target_brake(
    "yellow", 28, pid_approach,
    stop_pixels=15000,
    brake_speed=14,
    brake_pixel=8000,
)
```

**签名：** `approach_target_brake(color, forward_speed, pid_params, stop_pixels, brake_speed, brake_pixel)`

### 传参（main 里常改）

| 参数 | 说明 | 标定建议 |
|------|------|----------|
| `color` | 目标色 | 同 `approach_target` |
| `forward_speed` | 第一段较快 PWM | 22~32 |
| `pid_params` | PID 参数 | 同 §5 / v4 |
| `stop_pixels` | 最终停车面积 | debug 看 `px=` |
| `brake_speed` | 第二段较慢 PWM | 约为 `forward_speed` 的 40%~60% |
| `brake_pixel` | 开始减速的面积 | 约为 `stop_pixels` 的 50%~70% |

### Config（不常改）

与 `approach_target` 相同：`APPROACH_TIMEOUT`、`APPROACH_LOST_BACKUP_FRAMES`、HSV、`MAX_VALID_AREA`。

**注意：** 无丢目标恢复；需要恢复请用 `approach_target_recover` 或自行写逻辑。

### 返回值

| 值 | 含义 |
|----|------|
| `True` | 到达 `stop_pixels` |
| `False` | 超时或丢失过久 |

---

## 9. approach_target_recover(...) → bool 【v5 新增】

**功能：** 在 `approach_target` 基础上，若因**丢失目标**（非超时）失败，自动：编码器后退 → `search_color` → 再 `approach_target` 一次。

```
approach_target → 成功 → True
              → 丢目标 → forward_pid 后退 → search_color → approach_target → 返回第二次结果
              → 超时 → False（不恢复）
```

**签名：**

```text
approach_target_recover(
    color, forward_speed, pid_params, stop_pixels,
    backup_left=-40, backup_right=-40,
    backup_step=0.5, backup_interval=0.05, backup_duration=0.8,
    search_pwm=40, search_interval=0.3,
    use_left_wheel=False,
)
```

### 传参 — 靠近段（与 approach_target 相同，常改）

| 参数 | 说明 |
|------|------|
| `color`, `forward_speed`, `pid_params`, `stop_pixels` | 同 `approach_target` |

### 传参 — 恢复段（有默认值，赛段需要时再改）

| 参数 | 默认 | 说明 |
|------|------|------|
| `backup_left` / `backup_right` | -40, -40 | 后退 `forward_pid` 初速度 |
| `backup_step` | 0.5 | 后退时编码器同步步长 |
| `backup_interval` | 0.05 | 后退修正间隔（秒） |
| `backup_duration` | 0.8 | 后退时长（秒） |
| `search_pwm` | 40 | 恢复搜色驱动轮 PWM |
| `search_interval` | 0.3 | 恢复搜色每步时长 |
| `use_left_wheel` | False | 恢复搜色用左轮或右轮 |

### Config（不常改）

| 字段 | 影响 |
|------|------|
| `APPROACH_TIMEOUT` | 每次 `approach_target` 子调用 |
| `APPROACH_LOST_BACKUP_FRAMES` | 子调用内丢目标 retry |
| `SEARCH_*` | 恢复阶段 `search_color` |
| HSV / `MAX_VALID_AREA` | 识别 |

后退段内部用 `forward_pid`，还受编码器引脚等 v4 Config 影响。

### 返回值

| 值 | 含义 |
|----|------|
| `True` | 首次或恢复后靠近成功 |
| `False` | 超时、搜色失败、或恢复后仍失败 |

---

## 10. turn_angle(angle_deg, speed, step) 【v5 新增】

**功能：** 编码器闭环原地转指定**角度**；正=逆时针左转，负=顺时针右转。

```python
turn_angle(90, 50, 0.2)     # 左转 90°
turn_angle(-75, 45, 0.2)    # 右转 75°
```

### 传参（main 里常改）

| 参数 | 说明 | 典型值 |
|------|------|--------|
| `angle_deg` | **正=左转，负=右转**（度） | 45, 90, -90 |
| `speed` | 转弯 PWM 幅度（正数） | 40~55 |
| `step` | 左右同步修正步长 | 0.2~0.5 |

### Config（现场标定，不常改）

| 字段 | 作用 |
|------|------|
| `WHEEL_DIAMETER_CM` | 角度 ↔ 脉冲换算 |
| `TRACK_WIDTH_CM` | 角度 ↔ 脉冲换算 |
| `TURN_CALIB` | 转不够/转过头 |
| `ENC_FINISH_PULSES` | 惯性过冲 |
| `ENC_TIMEOUT_S` | 打滑超时 |
| `ENC_LOOP_INTERVAL` | 控制周期 |
| `ENC_SWAP` | 左右脉冲对调 |
| `ENCODER_PULSES_PER_REV` | 脉冲密度 |
| `LEFT_ENCODER` / `RIGHT_ENCODER` | 接线 |

可替代 `turn_left(duration, wheel_speed)`；重复性更好，推荐用传参 `angle_deg` 而非猜时间。

---

## 11. 开环 / 按时间编码器 API（与 v4 相同）

| API | 传参（常改） | Config（不常改） |
|-----|--------------|------------------|
| `turn_left` / `turn_right` | `duration`, `wheel_speed` | `SWAP_WHEELS`, `INVERT_*` |
| `forward_time` | `left_speed`, `right_speed`, `duration` | `SWAP_WHEELS`, `INVERT_*` |
| `forward_pid` | `left/right_speed`, `step`, `interval`, `duration` | 编码器引脚 |

详见 [cube_v4.md §9](./cube_v4.md#9-开环--编码器运动-api)。

---

## 12. 函数一览

| 函数 | 类型 | 主要传参 | 主要 Config |
|------|------|----------|-------------|
| `setup` | 生命周期 | `dry_run`, `show_debug` | 全局 `CFG` |
| `cleanup` | 生命周期 | — | — |
| `show_debug` | 调试 | `state`, `det` | `SHOW_DEBUG` |
| `search_color` | 视觉 | `wheel_pwm`, `interval`, `color`, `use_left_wheel` | `SEARCH_*`, HSV |
| `approach_target` | 视觉 | `color`, `forward_speed`, `pid`, `stop_pixels` | `APPROACH_*`, HSV |
| `approach_target_brake` | 视觉 | + `brake_speed`, `brake_pixel` | 同 approach |
| `approach_target_recover` | 视觉 | + `backup_*`, `search_*` | 同 approach + search |
| `turn_angle` | 编码器 | `angle_deg`, `speed`, `step` | `TURN_CALIB`, 轮距, `ENC_*` |
| `turn_left` / `turn_right` | 开环 | `duration`, `wheel_speed` | 电机方向 |
| `forward_time` | 开环 | `left`, `right`, `duration` | 电机方向 |
| `forward_pid` | 编码器 | `left`, `right`, `step`, `interval`, `duration` | 编码器引脚 |

---

## 13. 典型比赛流程（参考 __main__）

```
靠近蓝 → 左转 → 直行 → 搜黄 → 靠近黄 → 右转 → 直行 → 搜红 → ...
→ 靠近红 → 左转 → 直行 → 搜蓝 → 靠近蓝 → 左转 → 直行 → 搜红
→ 靠近红 → 右转 → 直行 → 左转 → 长直行冲线
```

可将 `turn_left` 换成 `turn_angle`；将 `approach_target` 换成 `approach_target_recover` / `approach_target_brake`：

```python
approach_target_recover("blue", 28, pid_approach, stop_pixels=15000)
turn_angle(90, 50, 0.2)
forward_pid(40, 40, 0.5, 0.05, 0.8)

search_color(-40, 0.3, "yellow")
approach_target_brake("yellow", 28, pid_approach, stop_pixels=15000, brake_speed=14, brake_pixel=8000)
```

---

## 14. v5 临场标定清单

在 [cube_v4.md §12](./cube_v4.md#12-临场标定清单) 基础上：

| 标定项 | 怎么标 | 传参 or Config |
|--------|--------|----------------|
| 转弯角度 | `turn_angle(90,50,0.2)` 量角度 | **Config** `TURN_CALIB`, `TRACK_WIDTH_CM`；**传参** `angle_deg` |
| 到位过冲 | 停点后仍滑 | **Config** `ENC_FINISH_PULSES` |
| 直行仍漂 | 长距离弯一侧 | **传参** `forward_pid` 的 `step` |
| 左/右轮搜色 | 步进方向 | **传参** `wheel_pwm` 正负 + `use_left_wheel` |
| 减速靠近 | 避免冲过头 | **传参** `brake_pixel`, `brake_speed` |
| 丢目标恢复 | 跟丢后能否找回 | **传参** `backup_duration`, `search_pwm` |
| 编码器左右反 | 角度符号怪 | **Config** `ENC_SWAP` |

---

## 15. 常见问题（v5 补充）

**Q: v5 可以直接替代 v4 吗？**  
A: 可以。不传 v5 新参数时，`search_color` 与 v4 右轮行为一致。

**Q: `approach_target_recover` 和 `approach_target` 该用哪个？**  
A: 稳定赛段用 `approach_target`；易跟丢用 `approach_target_recover`。

**Q: `approach_target_brake` 丢目标会恢复吗？**  
A: 不会。需要恢复用 `approach_target_recover`。

**Q: `turn_angle` 和 `turn_left` 该用哪个？**  
A: 需要 repeatable 的 90°/45° 用 `turn_angle`；临时微调可用开环 `turn_left`。

**Q: 编码器记到反轮上了怎么办？**  
A: 试 `CFG.ENC_SWAP = True`（与 `SWAP_WHEELS` 独立，专管脉冲左右）。

**Q: 哪些参数写在 main，哪些写 Config？**  
A: 每个 API 上文 **传参** 表 = main 常改；**Config** 表 = 接线/标定后偶尔改。完整 Config 分类见 v4 §4 + 本文 §3。
