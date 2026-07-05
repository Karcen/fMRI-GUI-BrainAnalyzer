#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 主题样式 — Brain Analyzer v2.0"""
from PyQt5.QtCore import Qt

MONO = "Menlo, Monaco, 'Courier New', monospace"


class StyleManager:
    PRIMARY = "#0078d4"

    # ─── Light ────────────────────────────────────────────────────────────────
    def get_light_theme(self) -> str:
        return """
        /* ── Window & base ─── */
        QMainWindow { background: #f5f7fa; }
        QWidget      { background: transparent; color: #1d2433; font-size: 12px; }

        /* ── Left panel background ─── */
        QWidget#leftPanel { background: #f5f7fa; }

        /* ── Card-style GroupBox ─── */
        QGroupBox {
            background: white;
            border: 1px solid #e1e6ed;
            border-radius: 8px;
            margin-top: 16px;
            padding: 10px 10px 8px 10px;
            font-size: 12px;
            font-weight: 600;
            color: #333d4b;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: -1px;
            padding: 0 6px;
            background: #f5f7fa;
            color: #0078d4;
            font-size: 12px;
            font-weight: 700;
        }

        /* ── Buttons ─── */
        QPushButton {
            background: #0078d4;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 600;
            min-height: 32px;
        }
        QPushButton:hover   { background: #106ebe; }
        QPushButton:pressed { background: #005a9e; }
        QPushButton:disabled { background: #dde3ea; color: #9aa3ae; }

        /* ── Start button (special) ─── */
        QPushButton#startBtn {
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                         stop:0 #0086ef, stop:1 #006cbf);
            font-size: 14px;
            min-height: 46px;
            border-radius: 8px;
        }
        QPushButton#startBtn:hover {
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                         stop:0 #1090f5, stop:1 #0078d4);
        }
        QPushButton#startBtn:disabled { background: #dde3ea; color: #9aa3ae; }

        /* ── Stop button ─── */
        QPushButton#stopBtn {
            background: #f0f4f8;
            color: #5a6476;
            border: 1px solid #dde3ea;
        }
        QPushButton#stopBtn:enabled { background: #fff1f0; color: #cf1322; border-color: #ffa39e; }
        QPushButton#stopBtn:hover   { background: #ffe7e6; }

        /* ── Progress bar ─── */
        QProgressBar {
            border: none;
            border-radius: 4px;
            background: #e8edf3;
            height: 8px;
            text-align: center;
            font-size: 10px;
            color: transparent;
        }
        QProgressBar::chunk { background: #0078d4; border-radius: 4px; }

        /* ── CheckBox — use native macOS rendering, just fix spacing ─── */
        QCheckBox {
            spacing: 6px;
            font-size: 12px;
            color: #1d2433;
        }
        QCheckBox:disabled { color: #9aa3ae; }

        /* ── Label ─── */
        QLabel { font-size: 12px; color: #1d2433; background: transparent; }

        /* ── Log / Result text area ─── */
        QTextEdit {
            background: #0d1117;
            color: #e6edf3;
            border: none;
            border-radius: 8px;
            font-family: """ + MONO + """;
            font-size: 12px;
            padding: 8px;
            selection-background-color: #264f78;
        }

        /* ── Tabs ─── */
        QTabWidget::pane {
            border: 1px solid #e1e6ed;
            border-top: none;
            border-radius: 0 0 8px 8px;
        }
        QTabBar::tab {
            background: #edf0f4;
            color: #5a6476;
            padding: 8px 20px;
            border: 1px solid #e1e6ed;
            border-bottom: none;
            border-radius: 6px 6px 0 0;
            margin-right: 2px;
            font-size: 12px;
        }
        QTabBar::tab:selected {
            background: white;
            color: #0078d4;
            font-weight: 700;
            border-bottom: 2px solid white;
        }
        QTabBar::tab:hover:!selected { background: #dde3ea; }

        /* ── Scroll area / scrollbar ─── */
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical {
            background: transparent;
            width: 6px;
            margin: 2px;
        }
        QScrollBar::handle:vertical {
            background: #c1c9d4;
            border-radius: 3px;
            min-height: 24px;
        }
        QScrollBar::handle:vertical:hover { background: #0078d4; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        /* ── ComboBox ─── */
        QComboBox {
            border: 1px solid #dde3ea;
            border-radius: 6px;
            padding: 5px 10px;
            background: white;
            font-size: 12px;
            color: #1d2433;
        }
        QComboBox:hover { border-color: #0078d4; }
        QComboBox::drop-down { border: none; width: 24px; }

        /* ── Status bar ─── */
        QStatusBar { background: #edf0f4; color: #5a6476; font-size: 11px; }
        QStatusBar::item { border: none; }

        /* ── Menu bar ─── */
        QMenuBar { background: #f5f7fa; border-bottom: 1px solid #e1e6ed; }
        QMenuBar::item { padding: 5px 10px; border-radius: 4px; }
        QMenuBar::item:selected { background: #0078d4; color: white; }

        /* ── Splitter ─── */
        QSplitter::handle { background: #e1e6ed; }
        """

    # ─── Dark ─────────────────────────────────────────────────────────────────
    def get_dark_theme(self) -> str:
        return """
        QMainWindow { background: #0d1117; }
        QWidget      { background: transparent; color: #e6edf3; font-size: 12px; }

        QGroupBox {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            margin-top: 16px;
            padding: 10px 10px 8px 10px;
            font-weight: 600;
            color: #e6edf3;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px; top: -1px;
            padding: 0 6px;
            background: #0d1117;
            color: #58a6ff;
            font-weight: 700;
        }

        QPushButton {
            background: #1f6feb;
            color: white; border: none; border-radius: 6px;
            padding: 7px 16px; font-size: 12px; font-weight: 600; min-height: 32px;
        }
        QPushButton:hover   { background: #388bfd; }
        QPushButton:pressed { background: #1158c7; }
        QPushButton:disabled { background: #21262d; color: #484f58; }

        QPushButton#startBtn {
            background: #1f6feb;
            font-size: 14px; min-height: 46px; border-radius: 8px;
        }
        QPushButton#startBtn:disabled { background: #21262d; color: #484f58; }

        QPushButton#stopBtn {
            background: #21262d; color: #8b949e;
            border: 1px solid #30363d;
        }
        QPushButton#stopBtn:enabled { background: #3d1f1f; color: #f85149; border-color: #6e2020; }
        QPushButton#stopBtn:hover   { background: #4a2424; }

        QProgressBar {
            border: none; border-radius: 4px;
            background: #21262d; height: 8px; color: transparent;
        }
        QProgressBar::chunk { background: #1f6feb; border-radius: 4px; }

        QCheckBox { spacing: 6px; font-size: 12px; color: #e6edf3; }
        QCheckBox:disabled { color: #484f58; }

        QLabel { font-size: 12px; color: #e6edf3; background: transparent; }

        QTextEdit {
            background: #010409; color: #e6edf3;
            border: none; border-radius: 8px;
            font-family: """ + MONO + """;
            font-size: 12px; padding: 8px;
        }

        QTabWidget::pane { border: 1px solid #30363d; border-radius: 0 0 8px 8px; }
        QTabBar::tab {
            background: #161b22; color: #8b949e;
            padding: 8px 20px; border: 1px solid #30363d;
            border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px;
        }
        QTabBar::tab:selected { background: #0d1117; color: #58a6ff; font-weight: 700; }
        QTabBar::tab:hover:!selected { background: #21262d; }

        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
        QScrollBar::handle:vertical { background: #30363d; border-radius: 3px; min-height: 24px; }
        QScrollBar::handle:vertical:hover { background: #1f6feb; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        QComboBox {
            border: 1px solid #30363d; border-radius: 6px;
            padding: 5px 10px; background: #161b22;
            font-size: 12px; color: #e6edf3;
        }
        QComboBox:hover { border-color: #1f6feb; }
        QComboBox::drop-down { border: none; width: 24px; }

        QStatusBar { background: #161b22; color: #8b949e; font-size: 11px; }
        QStatusBar::item { border: none; }
        QMenuBar { background: #0d1117; border-bottom: 1px solid #30363d; }
        QMenuBar::item { padding: 5px 10px; border-radius: 4px; }
        QMenuBar::item:selected { background: #1f6feb; color: white; }
        QSplitter::handle { background: #30363d; }
        """
