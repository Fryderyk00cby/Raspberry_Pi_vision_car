# 2026 魔方绕桩 — 五种情况说明

本目录为 **2026 年魔方绕桩** 任务准备，在 **cube_v4** 框架上针对五种赛道情况各写一套完整可运行脚本。每个 `adapt_*` 目录内的主 `.py` 为**自包含**文件（函数库 + 比赛流程），不 import 仓库根目录的 `cube_v4.py`。

赛道规则示意图见同目录 **`rule.png`**。

---

## 目录结构

```
2026_task/
├── rule.png                    # 赛道 / 规则示意图
├── 2026_version_example.md     # 本说明
├── adapt_LL/                   # 情况 LL
│   ├── LL.py                  # 主程序（函数库 + 比赛流程）
├── adapt_LR/                   # 情况 LR
│   ├── LR.py
├── adapt_MM/                   # 情况 MM
│   ├── MM.py
├── adapt_RL/                   # 情况 RL
│   ├── RL.py
└── adapt_RR/                   # 情况 RR
    ├── RR.py
```

---

## 五种情况命名

两个字母表示**第一个**与**第三个**方块的左右位置组合（详见 `rule.png`）：

| 目录 | 含义（示意） |
|------|----------------|
| `adapt_LL` | 第一块偏左，第三块偏左 |
| `adapt_LR` | 第一块偏左，第三块偏右 |
| `adapt_MM` | 第一、三块均居中 |
| `adapt_RL` | 第一块偏右，第三块偏左 |
| `adapt_RR` | 第一块偏右，第三块偏右 |

---

## 运行方式

在树莓派上进入对应目录，运行主程序，例如：

```bash
cd 2026_task/adapt_LL
python3 LL.py
```

---

## 与根目录库的关系

- 核心 API（`search_color`、`approach_target`、`turn_angle`、`forward_pid` 等）与根目录 **[cube_v4.md](../cube_v4.md)** 描述一致。
- 若只需通用函数库、自行拼接流程，请直接使用根目录的 `cube_v4.py` 或 `cube_v5.py`。
- 本目录脚本已内嵌 `turn_angle` 等增强，并按各赛道情况写好 `__main__` 流程，供课程项目参考与现场微调。
