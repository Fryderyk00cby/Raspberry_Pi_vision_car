#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_script 公共导入：把仓库根目录加入 sys.path，便于引用 cube_v4 / cube_v5。"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def import_cube(use_v5: bool = True):
    """默认加载 cube_v5；标定 turn_angle / forward_pid 时 v4 与 v5 接口相同。"""
    if use_v5:
        import cube_v5 as lib
    else:
        import cube_v4 as lib
    return lib
