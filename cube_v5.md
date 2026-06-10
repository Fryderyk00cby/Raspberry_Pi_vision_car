# cube_v5.py 使用说明

魔方绕桩任务的**可拼接函数库（v5 增强版）**。在 `cube_v4.py` 全部能力之上，新增左/右轮搜色、减速靠近、丢目标自动恢复等功能。

依赖：OpenCV、NumPy、树莓派上的 RPi.GPIO（非树莓派环境会自动进入 DRY_RUN，只打印电机指令）。

> v4 已有功能的详细说明（Config、PID、开环运动、标定清单等）见 **[cube_v4.md](./cube_v4.md)**。本文档重点说明 **v5 新增与变更** 部分，其余 API 与 v4 用法相同。

---

## 1. v5 相对 v4 的变更摘要

| 项目 | v4 | v5 |
|------|----|----|
| `search_color` 驱动轮 | 仅右轮（参数名 `right_pwm`） | 默认右轮；可选左轮（`use_left_wheel=True`） |
| 减速靠近 | 无 | `approach_target_brake` |
| 丢目标恢复 | 无 | `approach_target_recover` |
| `drive_blind` | 有（已删除） | 无，请用 `forward_time` |

---

## 2. 基本用法模板

```python
from cube_v5 import (
    setup, cleanup,
    search_color, approach_target, approach_target_recover,
    turn_left, forward_pid, PidParams,
)

setup(dry_run=False, show_debug=True)

pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

try:
    # 带丢目标恢复的靠近（推荐在容易跟丢的赛段使用）
    approach_target_recover("blue", 28, pid_approach, stop_pixels=15000)

    turn_left(0.2, 60)
    forward_pid(40, 40, 0.5, 0.05, 0.8)

    # 右轮搜色（默认，与 v4 行为一致）
    if search_color(-40, 0.3, "yellow"):
        approach_target("yellow", 28, pid_approach, stop_pixels=15000)

    # 左轮搜色
    if search_color(40, 0.3, "red", use_left_wheel=True):
        approach_target("red", 28, pid_approach, stop_pixels=6000)
except KeyboardInterrupt:
    pass
finally:
    cleanup()
```

| 步骤 | 函数 | 说明 |
|------|------|------|
| 开头 | `setup()` | 初始化 GPIO、霍尔编码器、摄像头线程 |
| 中间 | 各种动作函数 | 见下文及 cube_v4.md |
| 结尾 | `cleanup()` | 停车、释放摄像头与 GPIO，务必放在 `finally` 里 |

---

## 3. search_color(wheel_pwm, interval, color, use_left_wheel=False) → bool

**单轮步进搜色**：固定一侧轮为 0，另一侧轮旋转 → 停车 → 等画面稳定 → 识别。

与 v4 的区别：第一个参数改名为 `wheel_pwm`（语义为「驱动轮」PWM）；新增第四个参数 `use_left_wheel`。

```python
search_color(40, 0.3, "blue")                           # 右轮（默认）
search_color(-40, 0.3, "yellow")                        # 右轮负转
search_color(40, 0.3, "red", use_left_wheel=True)       # 左轮
search_color(-40, 0.3, "yellow", use_left_wheel=True)  # 左轮负转
```

| 参数 | 说明 |
|------|------|
| `wheel_pwm` | 驱动轮 PWM，-100~100；另一侧轮恒为 0 |
| `interval` | 每步旋转时长（秒），建议 ≥ 0.02 |
| `color` | `"blue"` / `"yellow"` / `"red"`（或 蓝/黄/红） |
| `use_left_wheel` | `False`（默认）右轮驱动；`True` 左轮驱动 |

| 返回值 | 含义 |
|--------|------|
| `True` | 画面内已有色块，可接 `approach_target` |
| `False` | 在 `SEARCH_FULL_ROTATION_TIME` 内未找到 |

**何时用左轮：** 右轮搜色扫不到目标、或步进方向与赛道布局相反时，尝试切换 `use_left_wheel=True` 并调整 `wheel_pwm` 正负号。

---

## 4. approach_target(color, forward_speed, pid_params, stop_pixels) → bool

与 v4 完全相同。PID 直行靠近，色块面积达到 `stop_pixels` 后停车。

```python
approach_target("blue", forward_speed=28, pid_params=pid_approach, stop_pixels=15000)
```

| 返回值 | 含义 |
|--------|------|
| `True` | 已靠近到阈值 |
| `False` | 超时或长时间丢失目标 |

详见 [cube_v4.md §7](./cube_v4.md#7-approach_targetcolor-forward_speed-pid_params-stop_pixels--bool)。

---

## 5. approach_target_brake(...) → bool  【v5 新增】

**两段速度靠近**：先用较快 `forward_speed` 接近，色块面积达到 `brake_pixel` 后改用较慢的 `brake_speed`，达到 `stop_pixels` 后停止。适合防止冲过头。

```python
approach_target_brake(
    "yellow",
    forward_speed=28,
    pid_params=pid_approach,
    stop_pixels=15000,
    brake_speed=14,
    brake_pixel=8000,
)
```

| 参数 | 说明 |
|------|------|
| `forward_speed` | 靠近初期 PWM（较快） |
| `brake_speed` | 达到 `brake_pixel` 后的 PWM（较慢） |
| `brake_pixel` | 开始减速的轮廓面积阈值 |
| `stop_pixels` | 最终停止面积阈值 |

| 返回值 | 含义 |
|--------|------|
| `True` | 已靠近到 `stop_pixels` |
| `False` | 超时或长时间丢失目标 |

**标定建议：** 在 debug 窗口观察 `px=`，先确定最终停车距离对应的 `stop_pixels`，再取约 50%~70% 作为 `brake_pixel`，`brake_speed` 约为 `forward_speed` 的 40%~60%。

---

## 6. approach_target_recover(...) → bool  【v5 新增】

**带丢目标恢复的靠近**：在 `approach_target` 基础上，若尚未到达 `stop_pixels` 且因**丢失目标**失败，自动执行恢复流程。

```
approach_target
    ↓ 成功 → 返回 True
    ↓ 丢失目标
forward_pid 后退 0.8s（默认）
    ↓
search_color（默认右轮 pwm=40, interval=0.3）
    ↓ 找到
approach_target（再次靠近同一颜色）
    ↓
返回第二次靠近结果
```

```python
# 最简用法（全部默认参数）
approach_target_recover("blue", 28, pid_approach, stop_pixels=15000)

# 自定义恢复参数
approach_target_recover(
    "red", 28, pid_approach, stop_pixels=6000,
    backup_left=-40, backup_right=-40,
    backup_step=0.5, backup_interval=0.05,
    backup_duration=0.8,
    search_pwm=40, search_interval=0.3,
    use_left_wheel=False,
)
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `color`, `forward_speed`, `pid_params`, `stop_pixels` | — | 同 `approach_target` |
| `backup_left`, `backup_right` | -40, -40 | 后退 `forward_pid` 初速度 |
| `backup_step` | 0.5 | 后退编码器修正步长 |
| `backup_interval` | 0.05 | 后退修正间隔（秒） |
| `backup_duration` | 0.8 | 后退时长（秒） |
| `search_pwm` | 40 | 恢复搜色驱动轮 PWM |
| `search_interval` | 0.3 | 恢复搜色每步时长（秒） |
| `use_left_wheel` | False | 恢复搜色用左轮或右轮 |

| 返回值 | 含义 |
|--------|------|
| `True` | 首次或恢复后成功靠近 |
| `False` | 超时失败、搜色未找到、或恢复后仍失败 |

**注意：**

- 仅对**丢失目标**触发恢复；若因**超时**失败，不会后退搜色。
- 恢复流程只重试**一次** `approach_target`。
- 可直接替换原 `approach_target` 调用，成功时行为一致。

---

## 7. 开环 / 编码器函数

与 v4 相同，包括 `turn_left`、`turn_right`、`forward_time`、`forward_pid`。详见 [cube_v4.md §8](./cube_v4.md#8-开环运动函数)。

---

## 8. 函数一览

| 函数 | 类型 | 简要说明 |
|------|------|----------|
| `setup` | 生命周期 | 初始化硬件与摄像头 |
| `cleanup` | 生命周期 | 释放资源 |
| `show_debug` | 调试 | 刷新 imshow 窗口 |
| `search_color` | 视觉闭环 | 单轮步进搜色；**v5** 可选左/右轮 |
| `approach_target` | 视觉闭环 | PID 靠近色块 |
| `approach_target_brake` | 视觉闭环 | **v5** 两段速度减速靠近 |
| `approach_target_recover` | 视觉闭环 | **v5** 丢目标后退搜色再靠近 |
| `turn_left` | 开环 | 逆时针转 |
| `turn_right` | 开环 | 顺时针转 |
| `forward_time` | 开环 | 定时差速 |
| `forward_pid` | 编码器闭环 | 霍尔直行 |

---

## 9. 典型比赛流程（参考 __main__）

文件末尾 `if __name__ == "__main__"` 是一段完整绕桩示例：

```
靠近蓝 → 左转 → 直行 → 搜黄 → 靠近黄 → 右转 → 直行 → 搜红 → ...
→ 靠近红 → 左转 → 直行 → 搜蓝 → 靠近蓝 → 左转 → 直行 → 搜红
→ 靠近红 → 右转 → 直行 → 左转 → 长直行冲线
```

可将其中 `approach_target` 按需替换为 `approach_target_recover` 或 `approach_target_brake`：

```python
setup(dry_run=False, show_debug=True)
pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

# 第一段：已知蓝块在前方
approach_target_recover("blue", 28, pid_approach, stop_pixels=15000)
turn_left(0.2, 60)
forward_pid(40, 40, 0.5, 0.05, 0.8)

search_color(-40, 0.3, "yellow")
approach_target_brake("yellow", 28, pid_approach, stop_pixels=15000, brake_speed=14, brake_pixel=8000)
# ... 后续同理
```

---

## 10. v5 临场标定补充

在 [cube_v4.md §11](./cube_v4.md#11-临场标定清单) 基础上，v5 额外关注：

| 标定项 | 怎么标 | 改哪里 |
|--------|--------|--------|
| 左/右轮搜色方向 | 看每步是否扫向目标区域 | `search_color` 的 `wheel_pwm` 正负 + `use_left_wheel` |
| 减速靠近 | debug 看 `px=`，避免冲过头 | `approach_target_brake` 的 `brake_pixel` / `brake_speed` |
| 丢目标恢复 | 跟丢后能否重新找到 | `approach_target_recover` 的 `backup_duration`、`search_pwm` |
| 后退距离 | 后退后视野是否回到可搜色范围 | `backup_duration`、后退速度 |

---

## 11. 常见问题（v5 补充）

**Q: v5 可以直接替代 v4 吗？**  
A: 可以。不传 v5 新参数时，`search_color` 与 v4 右轮搜色行为一致；`approach_target` 等共有函数签名不变。

**Q: `approach_target_recover` 和 `approach_target` 该用哪个？**  
A: 稳定赛段用 `approach_target`；容易跟丢、遮挡多的赛段用 `approach_target_recover`。

**Q: 恢复时搜色用了左轮，正常流程还用右轮，可以吗？**  
A: 可以。`approach_target_recover` 的 `use_left_wheel` 只影响恢复阶段的 `search_color`，与前面手动搜色无关。

**Q: `approach_target_brake` 丢目标会恢复吗？**  
A: 不会。需要恢复请用 `approach_target_recover`，或在 `approach_target_brake` 失败后自行写后退 + `search_color` 逻辑。

**Q: 从 v4 迁移 search_color 要改什么？**  
A: 第一个参数名从 `right_pwm` 改为 `wheel_pwm`，位置参数不变；现有 `search_color(-40, 0.3, "yellow")` 无需修改。
