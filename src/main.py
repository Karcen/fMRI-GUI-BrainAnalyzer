#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入口点"""
import sys, os

def main():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    # ── 高 DPI 必须在 QApplication 创建前设置 ──────────────────────────────
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Brain Analyzer")
    app.setOrganizationName("NeuroLab")

    from gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
