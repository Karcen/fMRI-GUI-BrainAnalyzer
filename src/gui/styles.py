#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 主题样式"""
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

class StyleManager:
    PRIMARY = "#0078d4"

    def get_light_theme(self) -> str:
        return """
        QMainWindow, QWidget { background-color: #f5f5f5; color: #333; }
        QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 6px;
                    margin-top: 10px; padding: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background: #0078d4; color: white; border: none; border-radius: 5px;
                      padding: 6px 14px; font-size: 13px; min-height: 28px; }
        QPushButton:hover { background: #106ebe; }
        QPushButton:pressed { background: #005a9e; }
        QPushButton:disabled { background: #ccc; color: #888; }
        QProgressBar { border: 1px solid #ccc; border-radius: 4px; height: 18px; text-align: center; }
        QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
        QTextEdit { background: white; border: 1px solid #ccc; border-radius: 4px;
                    font-family: Consolas, Monaco, monospace; font-size: 12px; }
        QTabWidget::pane { border: 1px solid #ccc; }
        QTabBar::tab { padding: 6px 16px; }
        QTabBar::tab:selected { background: white; font-weight: bold; color: #0078d4; }
        QCheckBox { font-size: 13px; }
        QLabel { font-size: 12px; }
        QMenuBar { background: #f0f0f0; }
        QMenuBar::item:selected { background: #0078d4; color: white; }
        QStatusBar { background: #e8e8e8; font-size: 11px; }
        """

    def get_dark_theme(self) -> str:
        return """
        QMainWindow, QWidget { background-color: #1e1e1e; color: #d4d4d4; }
        QGroupBox { font-weight: bold; border: 1px solid #555; border-radius: 6px;
                    margin-top: 10px; padding: 8px; color: #d4d4d4; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background: #0e639c; color: white; border: none; border-radius: 5px;
                      padding: 6px 14px; font-size: 13px; min-height: 28px; }
        QPushButton:hover { background: #1177bb; }
        QPushButton:pressed { background: #0a4e7d; }
        QPushButton:disabled { background: #444; color: #777; }
        QProgressBar { border: 1px solid #555; border-radius: 4px; height: 18px;
                       background: #2d2d2d; text-align: center; }
        QProgressBar::chunk { background: #0e639c; border-radius: 3px; }
        QTextEdit { background: #252526; color: #d4d4d4; border: 1px solid #555;
                    border-radius: 4px; font-family: Consolas, Monaco, monospace; font-size: 12px; }
        QTabWidget::pane { border: 1px solid #555; }
        QTabBar::tab { background: #2d2d2d; color: #ccc; padding: 6px 16px; }
        QTabBar::tab:selected { background: #1e1e1e; font-weight: bold; color: #4fc3f7; }
        QCheckBox { font-size: 13px; color: #d4d4d4; }
        QLabel { font-size: 12px; color: #d4d4d4; }
        QMenuBar { background: #2d2d2d; color: #d4d4d4; }
        QMenuBar::item:selected { background: #0e639c; }
        QStatusBar { background: #252526; color: #999; font-size: 11px; }
        QSplitter::handle { background: #444; }
        """
