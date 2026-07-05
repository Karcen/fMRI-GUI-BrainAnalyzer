#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brain Analyzer v2.0 启动脚本
自动使用含 PyQt5 + 完整科学栈的 Anaconda Python
用法: python launcher.py
      或直接双击
"""
import os, sys

ANACONDA_PY = "/opt/anaconda3/bin/python"

# 若当前解释器没有 PyQt5，切换到 Anaconda
if os.path.isfile(ANACONDA_PY) and os.path.realpath(sys.executable) != os.path.realpath(ANACONDA_PY):
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        os.execv(ANACONDA_PY, [ANACONDA_PY] + sys.argv)

# sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
src_dir      = os.path.join(project_root, "src")
for p in (src_dir, project_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import main

if __name__ == "__main__":
    main()
