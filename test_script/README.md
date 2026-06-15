# test_script — 标定脚本说明

本目录提供比赛前**分项标定**用的独立脚本，均从仓库根目录的 `cube_v4.py` / `cube_v5.py` 导入函数库。  
默认在 **`test_script` 分支**维护；主分支 `main` 不含此目录。

---

## 目录

- [运行环境](#运行环境)
- [推荐标定顺序](#推荐标定顺序)
- [脚本一览](#脚本一览)
- [各脚本用法](#各脚本用法)
  - [calibrate_encoder.py](#calibrate_encoderpy)
  - [calibrate_turn_angle.py](#calibrate_turn_anglepy)
  - [calibrate_forward_pid.py](#calibrate_forward_pidpy)
  - [calibrate_open_loop_turn.py](#calibrate_open_loop_turnpy)
  - [calibrate_approach.py](#calibrate_approachpy)
  - [HSV_test.py（根目录）](#hsv_testpy根目录)
- [通用设置](#通用设置)
- [标定结果写到哪里](#标定结果写到哪里)
- [常见问题](#常见问题)

---

## 运行环境

- **硬件**：树莓派 + 双轮小车 + 霍尔编码器 + 摄像头
- **系统**：在仓库根目录执行（路径示例）：

```bash
cd ~/Raspberry_Pi_vision_car
python3 test_script/calibrate_encoder.py
```

- **图形界面**：除编码器 / 运动类脚本外，`calibrate_approach.py` 与根目录 `HSV_test.py` 需要 **VNC 或本地桌面**（`cv2.imshow` 调试窗口）。
- **干跑**：本目录脚本默认 `dry_run=False`（真车动）。在 Windows 上无 GPIO 时会自动干跑，仅适合看日志，不能代替车上标定。

---

## 推荐标定顺序

按依赖关系，建议第一次上车按此顺序做：

```
1. HSV_test.py          → 颜色能稳定识别
2. calibrate_encoder.py → 编码器接线、左右脉冲正常
3. calibrate_turn_angle.py → 转弯角度准
4. calibrate_forward_pid.py → 直行不漂、段长可控
5. calibrate_approach.py    → 停靠距离（stop_pixels）
6. calibrate_open_loop_turn.py → 可选，仅开环转弯时需要
```

编码器异常时，先不要标 `turn_angle` / `forward_pid`，否则结果不可靠。

---

## 脚本一览

| 脚本 | 标定对象 | 主要改动位置 |
|------|----------|--------------|
| `calibrate_encoder.py` | 霍尔编码器读数 | `CFG.ENC_SWAP`、接线 |
| `calibrate_turn_angle.py` | `turn_angle` 转角 | `CFG.TURN_CALIB`、`TRACK_WIDTH_CM` |
| `calibrate_forward_pid.py` | `forward_pid` 直行 | **传参** `step` / `interval` / `duration` |
| `calibrate_open_loop_turn.py` | `turn_left` / `turn_right` | **传参** `duration`、`wheel_speed` |
| `calibrate_approach.py` | `approach_target` 停距 | **传参** `stop_pixels`、`PidParams` |
| 根目录 `HSV_test.py` | 蓝 / 黄 / 红 HSV | `CFG.LOW_*` / `HIGH_*` |

---

## 各脚本用法

### calibrate_encoder.py

**作用**：不动车轮电机，只读编码器；用手拨动左轮或右轮，看终端里 L/R 计数是否增加。

```bash
python3 test_script/calibrate_encoder.py
```

**操作**：

1. 运行后按提示，分别手动转动左轮、右轮各几圈。
2. 只有左轮转时 L 应变、R 应几乎不变（右轮同理）。
3. `Ctrl+C` 结束。

**如何判断**：

| 现象 | 处理 |
|------|------|
| 转左轮但 R 在涨 | 试 `CFG.ENC_SWAP = True`（写在 `cube_v4.py` / `cube_v5.py` 的 `Config` 里） |
| 计数不涨 | 查编码器接线（默认左 GPIO 6、右 GPIO 12） |
| 转一整圈脉冲差很多 | 核对 `ENCODER_PULSES_PER_REV`（默认 585） |

---

### calibrate_turn_angle.py

**作用**：依次执行 `turn_angle(90)`、`turn_angle(-90)` 等，在地面上量实际转角，调 `TURN_CALIB`。

```bash
python3 test_script/calibrate_turn_angle.py
```

**操作**：

1. 打开脚本顶部 **临场修改区**，按需改 `TEST_ANGLES`、`TURN_SPEED`、`TURN_STEP`。
2. 小车摆正，车前方贴一条参考线或用量角器。
3. 按 Enter 开始；每次转完后在 `PAUSE_BETWEEN_S` 秒内量实际角度。
4. `Ctrl+C` 可提前结束。

**调参**：

| 现象 | 处理 |
|------|------|
| 系统性转不够（命令 90° 只转了 80°） | **加大** `CFG.TURN_CALIB`（如 0.5 → 0.55） |
| 系统性转过头 | **减小** `CFG.TURN_CALIB` |
| 左右转偏差不对称 | 微调 `TRACK_WIDTH_CM`，或检查 `ENC_SWAP` |
| 停点后还滑一段 | 增大 `ENC_FINISH_PULSES` |

改 `Config` 后保存 `cube_v4.py` / `cube_v5.py`，再重跑本脚本验证。

---

### calibrate_forward_pid.py

**作用**：重复执行 `forward_pid`，观察直行是否跑偏、同样参数跑多次是否长度一致。

```bash
python3 test_script/calibrate_forward_pid.py
```

**说明**：`forward_pid` **按时间停车**，不按厘米停。标定的是 `left/right` 速度、`step`、`interval`、`duration` 组合。

**操作**：

1. 修改脚本内 `LEFT_SPEED`、`RIGHT_SPEED`、`STEP`、`INTERVAL`、`DURATION`、`REPEAT`。
2. 地面贴起点线，每次跑完用尺量前进距离，记录与 `duration` 的对应关系。
3. 观察是否持续向一侧偏。

**调参**：

| 现象 | 处理 |
|------|------|
| 向一侧偏 | 增大 `step`，或略调左右初始速度差 |
| 左右抖、修正过猛 | 减小 `step` 或增大 `interval` |
| 段太短/太长 | 改 `duration`（写在比赛 `main` **传参**里，不是 Config） |

---

### calibrate_open_loop_turn.py

**作用**：标定开环 `turn_left` / `turn_right` 的 `duration` 与 `wheel_speed`（不读编码器）。

```bash
python3 test_script/calibrate_open_loop_turn.py
```

**适用**：尚未用好 `turn_angle`，或比赛里只需补很小一段角度时。  
**推荐**：主流程优先用 `calibrate_turn_angle.py`；本脚本为备选。

修改脚本内 `TESTS` 列表即可增删测试项，每项为 `(说明, 函数名, duration, wheel_speed)`。

---

### calibrate_approach.py

**作用**：`search_color` 找到色块后 `approach_target` 靠近，在调试窗口看 **`px=`**（轮廓面积），确定 `stop_pixels`。

```bash
python3 test_script/calibrate_approach.py
```

**前提**：已用 `HSV_test.py` 调好颜色；需要 VNC 看 `cv2.imshow` 窗口。

**操作**：

1. 修改 `COLOR`、`SEARCH_PWM`、`STOP_PIXELS`、`PID` 等。
2. 将魔方放在赛道典型位置，运行脚本。
3. 观察窗口中 `px=`：在**理想停距**时记下数值，写入比赛代码的 `stop_pixels=...`。
4. 首次可把 `STOP_PIXELS` 设大一些，避免还没看清就停太近。

v5 可将 `USE_LEFT_WHEEL = True` 改为用左轮搜色（与 `cube_v5.search_color` 一致）。

---

### HSV_test.py（根目录）

颜色标定不在 `test_script/` 内，使用仓库根目录脚本：

```bash
python3 HSV_test.py
```

1. 改脚本顶部 `LOW_*` / `HIGH_*`
2. 看 `mask` 窗口：魔方白、背景黑
3. 按 `1`/`2`/`3` 切换蓝/黄/红；按 `p` 打印 HSV 粘贴到 `cube_v4.py` / `cube_v5.py` 的 `Config`

详见根目录 [README.md](../README.md) 与 [cube_v4.md](../cube_v4.md)。

---

## 通用设置

每个标定脚本顶部都有类似配置：

```python
USE_V5 = True   # True → cube_v5；False → cube_v4
```

- 比赛用 **v5** 时保持 `True`（默认）。
- **v4** 与 **v5** 在 `turn_angle`、`forward_pid` 上传参方式相同；v5 多 `search_color(..., use_left_wheel=...)` 等 API。

`_common.py` 负责把仓库根目录加入 `sys.path`，**不要删**。

---

## 标定结果写到哪里

| 标定项 | 写在哪里 | 类型 |
|--------|----------|------|
| HSV 阈值 | `cube_v4.py` / `cube_v5.py` → `Config` | Config |
| 编码器左右反 | `ENC_SWAP` | Config |
| 转弯角度 | `TURN_CALIB`、`TRACK_WIDTH_CM`、`ENC_FINISH_PULSES` | Config |
| 转弯目标角 | `turn_angle(90)` 等 | **main 传参** |
| 直行段长 | `forward_pid(..., duration=...)` | **main 传参** |
| 直行纠偏 | `forward_pid` 的 `step`、`interval` | **main 传参** |
| 开环转弯 | `turn_left(duration, speed)` | **main 传参** |
| 停靠距离 | `approach_target(..., stop_pixels=...)` | **main 传参** |
| PID 手感 | `PidParams(kp=..., min_delta=...)` | **main 传参** |

**经验**：和「这一趟走多远、转几度、停多近」相关的 → **传参**；和「硬件、识别、全局修正系数」相关的 → **Config**。

完整 API 说明：[cube_v4.md](../cube_v4.md) · [cube_v5.md](../cube_v5.md)

---

## 常见问题

**Q: 在 `test_script/` 目录里 `python3 calibrate_xxx.py` 可以吗？**  
A: 可以。脚本通过 `_common.py` 定位仓库根目录，两种运行方式等价。

**Q: 标定改的是脚本还是 cube_v5.py？**  
A: 脚本里只改**测试用的临时参数**（如测哪些角度）；持久结果写在 **`cube_v4.py` / `cube_v5.py` 的 `Config`** 或你的比赛 **`main` 传参**里。

**Q: Windows 上能标定吗？**  
A: 无 GPIO 时只能干跑看日志；**角度、直行、靠近距离必须在树莓派真车上标**。

**Q: `calibrate_approach` 搜不到色？**  
A: 先跑 `HSV_test.py`；再调 `SEARCH_PWM`、`SEARCH_INTERVAL`，或换光照。

**Q: 和 `2026_task` 里的 `*_angle*.py` 有什么关系？**  
A: `2026_task` 是完整比赛流程样例；本目录是**通用分项标定**，不依赖具体赛道，标完把参数写进你自己的 `main` 即可。
