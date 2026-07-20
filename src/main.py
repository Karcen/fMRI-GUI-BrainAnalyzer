#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入口点"""
import sys, os

def main():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPalette, QColor

    # ── 高 DPI 必须在 QApplication 创建前设置 ──────────────────────────────
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Brain Analyzer")
    app.setOrganizationName("NeuroLab")

    # ── 锁定浅色主题：用 Fusion + 显式白底黑字 palette，屏蔽 macOS 系统深色渗透 ──
    app.setStyle("Fusion")
    pal = QPalette()
    white  = QColor("#ffffff"); black = QColor("#1a1a1a")
    light  = QColor("#f5f5f5"); gray  = QColor("#666666")
    blue   = QColor("#1565C0")
    pal.setColor(QPalette.Window,          light)
    pal.setColor(QPalette.WindowText,      black)
    pal.setColor(QPalette.Base,            white)
    pal.setColor(QPalette.AlternateBase,   light)
    pal.setColor(QPalette.Text,            black)
    pal.setColor(QPalette.Button,          white)
    pal.setColor(QPalette.ButtonText,      black)
    pal.setColor(QPalette.ToolTipBase,     white)
    pal.setColor(QPalette.ToolTipText,     black)
    pal.setColor(QPalette.PlaceholderText, gray)
    pal.setColor(QPalette.Highlight,       blue)
    pal.setColor(QPalette.HighlightedText, white)
    pal.setColor(QPalette.Link,            blue)
    pal.setColor(QPalette.Disabled, QPalette.Text,       gray)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, gray)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, gray)
    app.setPalette(pal)

    from gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
