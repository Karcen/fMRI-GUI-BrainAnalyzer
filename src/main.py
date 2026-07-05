#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入口点"""
import sys, os

def main():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Brain Analyzer")
    app.setOrganizationName("NeuroLab")
    # 高 DPI
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    from gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
