# Raspberry Pi Vision Car 树莓派纯视觉小车
2026版本测试满分方案

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)


基于树莓派的视觉小车控制库，面向**魔方绕桩**比赛任务。通过 OpenCV 识别蓝 / 黄 / 红三色魔方，结合 PID 视觉闭环与霍尔编码器运动控制，完成搜色、靠近、转弯与冲线等动作。

| 你能从这里得到什么 | 说明 |
|--------------------|------|
| **函数库** | `cube_v4.py` / `cube_v5.py`：可拼接 API，自行写 `main` 流程 |
| **2026 参考实现** | `2026_task/`：五种赛道布局各一套完整可运行脚本 + 规则说明 |
| **标定工具** | `test_script/`：编码器、转弯、直行、靠近等分项标定脚本 |
| **颜色标定** | 根目录 `HSV_test.py`：临场调 HSV 阈值 |

详细 API：[cube_v4.md](./cube_v4.md) · [cube_v5.md](./cube_v5.md)  
2026 五种情况说明：[2026_task/2026_version_example.md](./2026_task/2026_version_example.md)

---

## 目录

- [功能概览](#功能概览)
- [硬件要求](#硬件要求)
- [项目结构](#项目结构)
- [怎么选：函数库 / 2026 参考 / 标定](#怎么选函数库--2026-参考--标定)
- [传参 vs Config（调参改哪里）](#传参-vs-config调参改哪里)
- [环境依赖](#环境依赖)
- [快速开始](#快速开始)
- [核心 API 一览](#核心-api-一览)
- [调试模式](#调试模式)
- [临场标定清单](#临场标定清单)
- [注意事项](#注意事项)
- [许可证](#许可证)

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 颜色识别 | HSV 阈值检测蓝 / 黄 / 红魔方，支持最大轮廓筛选 |
| 视觉闭环 | `search_color` 步进搜色、`approach_target` PID 靠近色块 |
| 开环运动 | `turn_left` / `turn_right` 定时转弯、`forward_time` 定时差速 |
| 编码器闭环 | `forward_pid` 按时间直行，`turn_angle` 按角度转弯（v4/v5 均支持） |
| v5 增强 | 左/右轮搜色、减速靠近、丢目标自动恢复 |
| 调试支持 | `cv2.imshow` 实时画面、`dry_run` 模式（无 GPIO 时只打印电机指令） |
| 调参标定 | `HSV_test.py` + `test_script/` 分项标定脚本 |

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
├── cube_v4.py              # 主函数库（稳定版）
├── cube_v5.py                # v4 增强版（推荐新项目使用）
├── cube_v4.md / cube_v5.md   # 完整 API 文档
├── HSV_test.py               # HSV 颜色临场标定
├── test_script/              # （如果不擅使用的话直接在cube_v4框架里调可能效率更高）
│   ├── calibrate_encoder.py
│   ├── calibrate_turn_angle.py
│   ├── calibrate_forward_pid.py
│   ├── calibrate_approach.py
│   └── calibrate_open_loop_turn.py
├── 2026_task/                # 2026 规则五种赛道参考实现
│   ├── rule.png              # 赛道尺寸与布局示意图
│   ├── 2026_version_example.md
│   ├── RL.mp4                # RL 情况实机演示（README 顶部嵌入）
│   ├── adapt_LL/ … adapt_RR/ # 五种布局各一套自包含脚本
│   └── …
├── LICENSE
└── README.md
```

### 版本选择

| 版本 | 适用场景 |
|------|----------|
| **`cube_v4.py`** | 通用稳定版：已包含 `turn_angle`、`forward_pid`、`search_color`、`approach_target` |
| **`cube_v5.py`** | 在 v4 基础上增加：`approach_target_brake`、`approach_target_recover`、`search_color(..., use_left_wheel=...)` |

| 项目 | v4 | v5 |
|------|----|----|
| `search_color` | `search_color(right_pwm, interval, color)`（右轮步进） | `search_color(wheel_pwm, interval, color, use_left_wheel=False)`（可选左/右轮） |
| 减速靠近 | 无 | `approach_target_brake` |
| 丢目标恢复 | 无 | `approach_target_recover` |
| 其余核心能力 | 与 v5 共享（`turn_angle`、`forward_pid`、`approach_target` 等） | 与 v4 共享 |

### 关于 `2026_task`

面向 **2026 年电子系统导论「魔方绕桩」** 规则，提供五种赛道布局（LL / LR / MM / RL / RR）的参考满分流程：

| 目录 | 含义（蓝块 L7 + 红块 L6） |
|------|---------------------------|
| `adapt_LL` | 左 + 左 |
| `adapt_LR` | 左 + 右 |
| `adapt_MM` | 中 + 中 |
| `adapt_RL` | 右 + 左 |
| `adapt_RR` | 右 + 右 |

- 每个 `adapt_*/*.py` 为**自包含**文件（函数库 + 比赛流程），不 `import` 根目录 `cube_v4.py`，可整文件拷贝到树莓派运行。
- 赛道规则与临场选目录对照见 **[2026_task/2026_version_example.md](./2026_task/2026_version_example.md)**，示意图见 **`2026_task/rule.png`**。
- 上方演示视频为 **RL** 情况实机跑法，对应脚本 **`2026_task/adapt_RL/RL.py`**。

### 关于 `test_script`

比赛前分项标定用独立脚本，从根目录 `cube_v4.py` / `cube_v5.py` 导入函数库。推荐顺序：

```
HSV_test.py → calibrate_encoder → calibrate_turn_angle → calibrate_forward_pid → calibrate_approach
```

完整说明见 **[test_script/README.md](./test_script/README.md)**。

---

## 怎么选：函数库 / 2026 参考 / 标定

| 你的目标 | 从哪里开始 |
|----------|------------|
| 自己写比赛流程 | 根目录 `cube_v4.py` 或 `cube_v5.py`，在 `main` 里拼接 API |
| 2026 规则、五种赛道直接参考 | 读 `2026_task/2026_version_example.md`，运行对应 `adapt_*/*.py` |
| 上车前调参 | 先 `HSV_test.py`，再按 `test_script/README.md` 逐项标定 |
| 只改某一趟的距离/角度 | 改 `main` **传参**（如 `turn_angle(90)`、`stop_pixels=8000`） |
| 改硬件/识别/全局修正 | 改 `Config`（HSV、引脚、`TURN_CALIB` 等） |

---

## 传参 vs Config（调参改哪里）

| 类型 | 在哪里改 | 典型场景 |
|------|----------|----------|
| **传参** | `main` 里调用函数时 | `stop_pixels`、`angle_deg`、`forward_pid` 的 `duration` |
| **PidParams** | `PidParams(kp=..., min_delta=...)` | 靠近 PID 手感 |
| **Config (`CFG`)** | 源码 `Config` 或 `CFG.xxx = ...` | HSV、电机接线、分辨率、搜色/靠近超时、轮径与 CALIB |

**经验法则：** 和「这一趟走多远、转几度、停多近」相关的 → **传参**；和「硬件、识别、全局超时、系统性走短/走长」相关的 → **Config**。

每个 API 的传参表与 Config 表见 **[cube_v4.md §3~§9](./cube_v4.md)**、**[cube_v5.md §2~§12](./cube_v5.md)**。

---

## 环境依赖

> 若已完成课程全部实验，可跳过安装步骤。

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
3. 按 `1` / `2` / `3` 切换蓝 / 黄 / 红预览；按 `p` 打印 HSV 供粘贴到 `Config`
4. 按 `q` 退出

需图形界面（本地桌面或 VNC）；SSH 无 X11 转发时请用 VNC。

### 2. 编写比赛流程（函数库）

**v4 示例（开环转弯 + 按时间直行）：**

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

**v5 示例（编码器按角度 + 丢目标恢复）：**

```python
from cube_v5 import (
    setup, cleanup, search_color, approach_target_recover,
    turn_angle, forward_pid, PidParams,
)

setup(dry_run=False, show_debug=True)
pid = PidParams(kp=0.18, ki=0.0, kd=0.012, min_delta=8, max_delta=12)

try:
    approach_target_recover("blue", 28, pid, stop_pixels=15000)
    turn_angle(90)
    forward_pid(40, 40, 0.5, 0.05, 0.8)

    if search_color(-40, 0.3, "yellow"):
        approach_target_recover("yellow", 28, pid, stop_pixels=15000)
except KeyboardInterrupt:
    pass
finally:
    cleanup()
```

标定 `turn_angle` 前，先在 `Config` 里设置 `WHEEL_DIAMETER_CM`、`TRACK_WIDTH_CM`，再调 `TURN_CALIB`（详见 [cube_v5.md §3](./cube_v5.md)）。

### 3. 直接运行 2026 参考流程

对照当天赛道（见 `2026_task/rule.png` 或裁判公布的 L7、L6），进入对应目录运行：

```bash
# 示例：RL 情况（蓝右 + 红左）
cd 2026_task/adapt_RL
python3 RL.py
```

五种情况与目录对照见 **[2026_task/2026_version_example.md](./2026_task/2026_version_example.md)**。


## 核心 API 一览

| 函数 | 版本 | 类型 | 主要传参 | 主要 Config |
|------|------|------|----------|-------------|
| `setup` | v4/v5 | 生命周期 | `dry_run`, `show_debug` | 全局 `CFG` |
| `cleanup` | v4/v5 | 生命周期 | — | — |
| `search_color` | v4/v5 | 视觉 | `wheel_pwm`, `interval`, `color`；v5 加 `use_left_wheel` | `SEARCH_*`, HSV |
| `approach_target` | v4/v5 | 视觉 | `color`, `forward_speed`, `pid`, `stop_pixels` | `APPROACH_*`, HSV |
| `approach_target_brake` | **v5** | 视觉 | + `brake_speed`, `brake_pixel` | 同 approach |
| `approach_target_recover` | **v5** | 视觉 | + `backup_*`, `search_*` | 同 approach + search |
| `turn_angle` | v4/v5 | 编码器 | `angle_deg`（可选 `speed`,`step`） | `TURN_CALIB`, 轮距, `ENC_*` |
| `turn_left` / `turn_right` | v4/v5 | 开环 | `duration`, `wheel_speed` | 电机方向 |
| `forward_time` | v4/v5 | 开环 | `left`, `right`, `duration` | 电机方向 |
| `forward_pid` | v4/v5 | 编码器 | `left`, `right`, `step`, `interval`, `duration` | 编码器引脚 |

**速度约定：** 所有速度为 PWM 占空比，范围 **-100 ~ 100**；负值表示该轮反转。`turn_angle` 里 `speed` 传正数，方向由 `angle_deg` 符号决定。

---

## 调试模式

| 模式 | 用法 | 场景 |
|------|------|------|
| 干跑 | `setup(dry_run=True)` | 电脑上测识别逻辑，不驱动电机 |
| 关窗口 | `setup(show_debug=False)` | 无图形界面，仅 print 日志 |
| 远程看画面 | VNC 或 `ssh -X` | 在电脑上查看 `cv2.imshow` 窗口 |

摄像头默认 **320×240 @ 40fps**，降低分辨率以提升树莓派帧率。更换分辨率后须同步缩放面积阈值（面积约按分辨率平方比缩放），并重新标定 `stop_pixels`。

调试窗口显示 `px=` 轮廓面积，用于标定 `stop_pixels`；详见 [cube_v4.md §13](./cube_v4.md)。

---

## 可以赛前调试参数清单

| 标定项 | 方法 | 传参 or Config |
|--------|------|----------------|
| HSV 颜色 | 运行 `HSV_test.py` | **Config** `LOW_*` / `HIGH_*` |
| 编码器 | `test_script/calibrate_encoder.py` | **Config** `ENC_SWAP`、接线 |
| 搜色步进 | 调 `wheel_pwm`、`interval`；v5 可选左/右轮 | **传参** `search_color` |
| 搜色等待 / 总超时 | 画面稳不稳、能否扫完 | **Config** `SEARCH_COLOR_SETTLE_TIME`、`SEARCH_FULL_ROTATION_TIME` |
| 靠近距离 | debug 窗口看 `px=` 或 `calibrate_approach.py` | **传参** `stop_pixels` |
| PID 手感 | 抖/慢/冲 | **传参** `PidParams` |
| 转弯（开环） | `calibrate_open_loop_turn.py` | **传参** `turn_left` / `turn_right` |
| 直行（按时间） | `calibrate_forward_pid.py` | **传参** `forward_pid` 的 `duration`、`step` |
| 转弯（按角度） | `calibrate_turn_angle.py` | **传参** `angle_deg`；**Config** `TURN_CALIB`、`TRACK_WIDTH_CM` |
| 停点过冲 | 到位仍滑 | **Config** `ENC_FINISH_PULSES` |
| 电机方向 | 前进变后退 | **Config** `SWAP_WHEELS` / `INVERT_*` |
| 编码器左右反 | 距离/角度符号怪 | **Config** `ENC_SWAP` |

完整分表见 [cube_v4.md §12](./cube_v4.md)、[cube_v5.md §14](./cube_v5.md)、[test_script/README.md](./test_script/README.md)。

---

## 注意事项

- 所有动作函数必须在 `setup()` 之后、`cleanup()` 之前调用。
- 比赛脚本建议用 `try / except KeyboardInterrupt / finally: cleanup()` 包裹，避免异常时电机不停。
- 红色在 HSV 中跨越 0° 与 180°，需分别配置 `RED1` 与 `RED2` 两段阈值。
- 非树莓派环境无法使用真实 GPIO，适合离线调试视觉与流程逻辑。
- v4/v5 的 `turn_angle` 都依赖轮径、轮距与 `TURN_CALIB`，首次上车务必在地面标定后再写比赛流程。
- `2026_task` 脚本为参考实现，现场仍需根据光照、起点位置微调 `__main__` 中的角度与直行参数，不过差异应该不大。

---

## 许可证

本项目采用 [MIT License](./LICENSE) 开源。

使用前请根据实际硬件与赛道条件完成标定与测试；比赛现场表现取决于标定质量，代码按「原样」提供，不作性能保证。
