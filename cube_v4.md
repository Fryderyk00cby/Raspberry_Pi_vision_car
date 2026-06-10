# cube_v4.py 使用说明

魔方绕桩任务的**可拼接函数库**。本文件不提供固定比赛流程，只提供「初始化 → 视觉/运动函数 → 清理」积木块，由你在 `main` 里按顺序拼接。

依赖：OpenCV、NumPy、树莓派上的 RPi.GPIO（非树莓派环境会自动进入 DRY_RUN，只打印电机指令）。

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

## 3. Config 配置项

全局配置在 `CFG = Config()`，比赛前按现场修改。常用项如下。

### 摄像头

| 字段 | 默认 | 说明 |
|------|------|------|
| `CAMERA_ID` | 0 | 摄像头设备号 |
| `WIDTH` / `HEIGHT` | 320 / 240 | 分辨率，降低可换更高帧率 |
| `FPS` | 40 | 目标帧率 |
| `SHOW_DEBUG` | True | 是否显示调试窗口 |

### HSV 颜色阈值

| 字段 | 颜色 |
|------|------|
| `LOW_RED1` / `HIGH_RED1` | 红色（H 接近 0） |
| `LOW_RED2` / `HIGH_RED2` | 红色（H 接近 180） |
| `LOW_YELLOW` / `HIGH_YELLOW` | 黄色 |
| `LOW_BLUE` / `HIGH_BLUE` | 蓝色 |

临场标定：用同目录下的 `HSV_test.py` 调 mask，再把数值粘贴到这里。

### 视觉面积阈值（与分辨率相关）

| 字段 | 默认 @320×240 | 用途 |
|------|---------------|------|
| `APPROACH_STOP_PIXELS` | 21000 | 靠近停止参考值 |
| `MAX_VALID_AREA` | 80000 | 过大轮廓视为误检 |

640×480 换 320×240 时，面积约 ×0.25。例如：85000→21000。

### 搜索 / 靠近

| 字段 | 默认 | 说明 |
|------|------|------|
| `SEARCH_FULL_ROTATION_TIME` | 10 s | `search_color` 总搜索超时 |
| `SEARCH_COLOR_SETTLE_TIME` | 0.5 s | `search_color` 每步停车后等待稳定 |
| `APPROACH_TIMEOUT` | 15 s | 靠近超时 |
| `APPROACH_LOST_BACKUP_FRAMES` | 10 | 丢失目标后先倒车几帧再放弃 |

---

## 4. PID 参数 PidParams

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

## 5. 生命周期函数

### setup(dry_run=False, show_debug=True)

主程序**开头调用一次**。初始化：

- 视觉模块 `Vision`
- 电机 `Car`（GPIO PWM）
- 霍尔编码器 `WheelEncoder`（后台线程）
- 摄像头 `CameraThread`（后台线程）

### cleanup()

主程序**结束或异常时调用**。停止编码器、停车、释放摄像头、清理 GPIO、关闭 OpenCV 窗口。

### show_debug(state, det=None)

各闭环函数内部已自动调用，一般无需手动写。若自己写识别循环，可传入状态文字和检测结果刷新调试画面。

---

## 6. search_color(right_pwm, interval, color) → bool

**右轮步进搜色**：左轮恒为 0，右轮转一小段 → 停车 → 等画面稳定（默认 0.5s）→ 识别。

```python
search_color(-40, 0.3, "yellow")   # 右轮负转，每步 0.3 秒
search_color(40, 0.3, "red")       # 右轮正转
```

| 参数 | 说明 |
|------|------|
| `right_pwm` | 右轮 PWM，-100~100 |
| `interval` | 每步旋转时长（秒），建议 ≥ 0.02 |
| `color` | `"blue"` / `"yellow"` / `"red"`（或 蓝/黄/红） |

| 返回值 | 含义 |
|--------|------|
| `True` | 画面内已有色块，可接 `approach_target` |
| `False` | 在 `SEARCH_FULL_ROTATION_TIME` 内未找到 |

识别标准与 `approach_target` 一致：最大色块面积在 `[1, MAX_VALID_AREA]` 即视为找到。

**典型用法：**

```python
if search_color(40, 0.3, "red"):
    approach_target("red", 28, pid_approach, stop_pixels=6000)
```

---

## 7. approach_target(color, forward_speed, pid_params, stop_pixels) → bool

**PID 直行靠近**指定颜色魔方，色块面积达到 `stop_pixels` 后停车。

```python
approach_target("blue", forward_speed=28, pid_params=pid_approach, stop_pixels=15000)
```

| 参数 | 说明 |
|------|------|
| `forward_speed` | 前进基础 PWM（左右轮同向） |
| `stop_pixels` | 轮廓面积达到此值停止 |

| 返回值 | 含义 |
|--------|------|
| `True` | 已靠近到阈值 |
| `False` | 超时或长时间丢失目标（会短暂倒车 retry） |

**丢目标行为：** 连续丢失时先以 `-forward_speed * 0.5` 倒车，超过 `APPROACH_LOST_BACKUP_FRAMES` 帧仍找不到则返回 `False`。

**stop_pixels 标定：** 在 `show_debug` 窗口看 `px=` 数值。离方块越近 px 越大，在合适停车距离读数即为参考值。

---

## 8. 开环运动函数

不依赖视觉，按时间或编码器执行。执行完自动 `stop()`。

### turn_left(duration, wheel_speed)

逆时针原地转，持续 `duration` 秒。

```python
turn_left(0.2, 60)   # 左转 0.2 秒，轮速 60
```

### turn_right(duration, wheel_speed)

顺时针原地转。

```python
turn_right(0.2, 60)
```

### forward_time(left_speed, right_speed, duration)

按给定左右轮速度行驶一段时间。

```python
forward_time(50, 50, 0.8)    # 直行前进
forward_time(-25, -25, 0.8)  # 直行后退
forward_time(20, -20, 0.5)   # 原地旋转
```

### forward_pid(left_speed, right_speed, step, interval, duration)

**霍尔编码器闭环直行**：每隔 `interval` 读左右轮转速，左快则左减右加，保持直线。

```python
forward_pid(40, 40, step=0.5, interval=0.05, duration=0.8)
```

| 参数 | 说明 |
|------|------|
| `left_speed`, `right_speed` | 初始 PWM |
| `step` | 每次修正步长（如 0.2 ~ 0.5） |
| `interval` | 修正间隔（秒，如 0.01 ~ 0.05） |
| `duration` | 总行驶时间（秒） |

适合长距离直行；短距离可用 `forward_time`。

---

## 9. 函数一览

| 函数 | 类型 | 简要说明 |
|------|------|----------|
| `setup` | 生命周期 | 初始化硬件与摄像头 |
| `cleanup` | 生命周期 | 释放资源 |
| `show_debug` | 调试 | 刷新 imshow 窗口 |
| `search_color` | 视觉闭环 | 右轮步进搜色 |
| `approach_target` | 视觉闭环 | PID 靠近色块 |
| `turn_left` | 开环 | 逆时针转 |
| `turn_right` | 开环 | 顺时针转 |
| `forward_time` | 开环 | 定时差速 |
| `forward_pid` | 编码器闭环 | 霍尔直行 |

---

## 10. 典型比赛流程（参考 __main__）

文件末尾 `if __name__ == "__main__"` 是一段完整绕桩示例，逻辑如下：

```
靠近蓝 → 左转 → 直行 → 搜黄 → 靠近黄 → 右转 → 直行 → 搜红 → ...
→ 靠近红 → 左转 → 直行 → 搜蓝 → 靠近蓝 → 左转 → 直行 → 搜红
→ 靠近红 → 右转 → 直行 → 左转 → 长直行冲线
```

对应代码片段：

```python
setup(dry_run=False, show_debug=True)
pid_approach = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

# 第一段：已知蓝块在前方，直接靠近
approach_target("blue", 28, pid_approach, stop_pixels=15000)
turn_left(0.2, 60)
forward_pid(40, 40, 0.5, 0.05, 0.8)

# 搜下一个颜色
search_color(-40, 0.3, "yellow")
approach_target("yellow", 28, pid_approach, stop_pixels=15000)
# ... 后续同理
```

你可以复制 `__main__` 为起点，只改时间、速度、`stop_pixels` 和顺序。

---

## 11. 临场标定清单

| 标定项 | 怎么标 | 改哪里 |
|--------|--------|--------|
| HSV 颜色 | 运行 `HSV_test.py` 看 mask | `Config` 的 `LOW_*` / `HIGH_*` |
| 搜色步进 | 调 `right_pwm`、`interval` 使每步能扫到新区域且不太冲 | `search_color` 参数 |
| 搜色停车等待 | 画面糊就加长，步数少就缩短 | `SEARCH_COLOR_SETTLE_TIME` |
| 搜色总超时 | 全场扫不完就加大 | `SEARCH_FULL_ROTATION_TIME` |
| 靠近停止距离 | debug 窗口看 `px=` | `stop_pixels` 参数 |
| 转弯角度 | 在地板上量 90° / 45° 对应 `duration` + `wheel_speed` | `turn_left` / `turn_right` |
| 直行距离 | 量一段赛道长度对应 `forward_pid` 的 `duration` | `forward_pid` 参数 |
| 编码器直行 | 长直线是否跑偏，调 `step` | `forward_pid` 的 `step` |

---

## 12. 调试画面

`SHOW_DEBUG=True` 时，窗口显示：

- 画面竖直中心线（对准参考）
- 色块矩形框、中心点
- `px=` 轮廓面积（标定 `stop_pixels` 用）
- 当前状态文字（如 `approach blue`）

远程查看：VNC 连树莓派，或 SSH -X 转发 X11。

---

## 13. 常见问题

**Q: 提示「请先调用 setup()」**  
A: 在调用任何动作函数前先 `setup()`。

**Q: 识别不到颜色**  
A: 先跑 `HSV_test.py` 标定 HSV；检查光照、摄像头是否脏。

**Q: search_color 找到了但 approach 立刻丢**  
A: 可能 stop_pixels 过大/过小，或 forward_speed 太快；降低速度或调整阈值。

**Q: 车走不直**  
A: 短距离用 `forward_time`；长距离用 `forward_pid` 并标定 `step`。

**Q: 在 Windows 上 import 报错 GPIO**  
A: 正常，会自动 DRY_RUN；要测识别请 `setup(dry_run=True)` 并接摄像头。
