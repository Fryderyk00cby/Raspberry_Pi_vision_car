# Raspberry Pi Vision Car — 魔方绕桩

基于树莓派的视觉小车控制库，面向**魔方绕桩**比赛任务。通过 OpenCV 识别蓝 / 黄 / 红三色魔方，结合 PID 视觉闭环与霍尔编码器直行，在赛道上完成搜色、靠近、转弯与冲线等动作。

本仓库提供**可拼接的动作函数库**，不包含固定比赛流程——你需要在 `main` 里按现场赛道自行组合 `setup` → 动作函数 → `cleanup`。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 颜色识别 | HSV 阈值检测蓝 / 黄 / 红魔方，支持最大轮廓筛选 |
| 视觉闭环 | `search_color` 步进搜色、`approach_target` PID 靠近色块 |
| 运动控制 | 开环转弯 / 定时直行、霍尔编码器闭环 `forward_pid` |
| 调试支持 | `cv2.imshow` 实时画面、`dry_run` 模式（无 GPIO 时只打印电机指令） |
| 临场标定 | 独立脚本 `HSV_test.py` 调 HSV 阈值 |

---

## 硬件要求

- 树莓派（推荐带摄像头模块或 USB 摄像头）
- 双轮差速小车 + L298N（或同类）电机驱动
- 霍尔编码器（左轮 GPIO 6，右轮 GPIO 12）
- 默认引脚配置见 `Config`（可在 `cube_v4.py` / `cube_v5.py` 顶部修改）

| 模块 | 默认 GPIO |
|------|-----------|
| 左轮 PWM / IN1 / IN2 | 13 / 26 / 19 |
| 右轮 PWM / IN1 / IN2 | 16 / 20 / 21 |
| 左 / 右编码器 | 6 / 12 |

若左右轮装反或方向相反，修改 `Config` 中的 `SWAP_WHEELS`、`INVERT_LEFT`、`INVERT_RIGHT`。

---

## 项目结构

```
Raspberry_Pi_vision_car/
├── cube_v4.py      # 主函数库（稳定版）
├── cube_v5.py      # v4 + approach_target_brake（带减速靠近）
├── HSV_test.py     # HSV 颜色临场标定工具
├── cube_v4.md      # cube_v4 详细 API 与调参说明
└── README.md
```

**版本选择：**

- 一般比赛流程用 **`cube_v4.py`** 即可。
- 需要「先快后慢」靠近色块时，用 **`cube_v5.py`** 的 `approach_target_brake`。

---

## 环境依赖

```bash
# 树莓派上
sudo apt install python3-opencv python3-numpy
pip3 install RPi.GPIO   # 部分系统已预装

# 非树莓派（仅测识别逻辑）
pip install opencv-python numpy
```

- Python 3.8+
- OpenCV、NumPy
- 树莓派运行时需要 `RPi.GPIO`；在 Windows / Mac 上会自动进入 **DRY_RUN**，只打印 `[MOTOR]` 日志，不驱动电机。

---

## 快速开始

### 1. HSV 颜色标定（比赛前必做）

```bash
python3 HSV_test.py
```

1. 修改脚本顶部的 `LOW_*` / `HIGH_*` 常量
2. 观察 `mask` 窗口：魔方应为白，背景尽量黑
3. 按 `1` / `2` / `3` 切换蓝 / 黄 / 红预览；按 `p` 打印 HSV 供粘贴到主程序 `Config`
4. 按 `q` 退出

需图形界面（本地桌面或 VNC）；SSH 无 X11 转发时请用 VNC。

### 2. 编写比赛流程

```python
from cube_v4 import setup, cleanup, search_color, approach_target, turn_left, forward_pid, PidParams

setup(dry_run=False, show_debug=True)
pid = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

try:
    if search_color(-40, 0.3, "blue"):
        approach_target("blue", 28, pid, stop_pixels=15000)
    turn_left(0.2, 60)
    forward_pid(40, 40, 0.5, 0.05, 0.8)
except KeyboardInterrupt:
    pass
finally:
    cleanup()
```

### 3. 直接运行示例流程

`cube_v4.py` / `cube_v5.py` 末尾 `if __name__ == "__main__"` 含完整绕桩示例：

```
靠近蓝 → 左转 → 直行 → 搜黄 → 靠近黄 → 右转 → 直行 → 搜红 → ...
→ 靠近红 → 左转 → 直行 → 搜蓝 → 靠近蓝 → 左转 → 直行 → 搜红
→ 靠近红 → 右转 → 直行 → 左转 → 长直行冲线
```

```bash
python3 cube_v4.py
```

---

## 核心 API 一览

| 函数 | 类型 | 说明 |
|------|------|------|
| `setup` | 生命周期 | 初始化 GPIO、编码器、摄像头 |
| `cleanup` | 生命周期 | 停车并释放资源（务必放在 `finally`） |
| `search_color` | 视觉闭环 | 右轮步进搜色，找到返回 `True` |
| `approach_target` | 视觉闭环 | PID 直行靠近，达到 `stop_pixels` 停止 |
| `approach_target_brake` | 视觉闭环 | **仅 v5**：到达 `brake_pixel` 后降速再停 |
| `turn_left` / `turn_right` | 开环 | 原地左转 / 右转 |
| `forward_time` | 开环 | 定时差速行驶 |
| `forward_pid` | 编码器闭环 | 霍尔反馈直行，减少跑偏 |
| `drive_blind` | 开环 | 盲开（同 `forward_time`） |

**速度约定：** 所有速度为 PWM 占空比，范围 **-100 ~ 100**；负值表示该轮反转。

更完整的参数说明、Config 字段、PID 调参见 **[cube_v4.md](./cube_v4.md)**。

---

## 调试模式

| 模式 | 用法 | 场景 |
|------|------|------|
| 干跑 | `setup(dry_run=True)` | 电脑上测识别逻辑，不驱动电机 |
| 关窗口 | `setup(show_debug=False)` | 无图形界面，仅 print 日志 |
| 远程看画面 | VNC 或 `ssh -X` | 在电脑上查看 `cv2.imshow` 窗口 |

摄像头默认 **320×240 @ 40fps**，降低分辨率以提升树莓派帧率。更换分辨率后须同步缩放面积阈值（面积约按分辨率平方比缩放）。

---

## 临场标定清单

| 标定项 | 方法 | 修改位置 |
|--------|------|----------|
| HSV 颜色 | 运行 `HSV_test.py` | `Config` 的 `LOW_*` / `HIGH_*` |
| 搜色步进 | 调 `right_pwm`、`interval` | `search_color` 参数 |
| 搜色等待 | 画面稳定时间 | `SEARCH_COLOR_SETTLE_TIME` |
| 靠近距离 | debug 窗口看 `px=` | `stop_pixels` |
| 转弯角度 | 量 90° 对应时长 | `turn_left` / `turn_right` |
| 直行距离 | 量赛道段长度 | `forward_pid` 的 `duration` |
| 编码器直行 | 长直线是否跑偏 | `forward_pid` 的 `step` |

---

## 注意事项

- 所有动作函数必须在 `setup()` 之后、`cleanup()` 之前调用。
- 比赛脚本建议用 `try / except KeyboardInterrupt / finally: cleanup()` 包裹，避免异常时电机不停。
- 红色在 HSV 中跨越 0° 与 180°，需分别配置 `RED1` 与 `RED2` 两段阈值。
- 非树莓派环境无法使用真实 GPIO，适合离线调试视觉与流程逻辑。

---

## 许可证

本项目为比赛/教学用途代码，使用前请根据实际硬件与赛道条件完成标定与测试。
