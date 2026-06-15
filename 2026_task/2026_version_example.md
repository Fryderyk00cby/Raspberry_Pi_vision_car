# 2026 魔方绕桩 — 五种情况说明

本目录为 **2026 年魔方绕桩** 任务准备，在 **cube_v4** ，针对五种赛道情况各写一套完整可运行脚本。

赛道规则示意图见同目录 **`rule.png`**。

---

## 目录结构

```
2026_task/
├── rule.png                 # 赛道 / 规则示意图
├── 2026_verse_example.md    # 本说明
├── adapt_LL/                # 情况 LL
│   ├── LL..py               # 主程序（函数库 + 比赛流程）
│   └── LL_angle_true.py     # 备用 / 标定版
├── adapt_LR/                # 情况 LR
│   ├── LR.py
│   └── LR_angle.py
├── adapt_MM/                # 情况 MM
│   ├── MM.py
│   └── MM_angle_true.py
├── adapt_RL/                # 情况 RL
│   ├── RL.py
│   └── RL_angle.py
└── adapt_RR/                # 情况 RR
    ├── RR.py
    └── RR_angle.py
```

两个字母表示第一个和第三个方块的左右位置的组合
