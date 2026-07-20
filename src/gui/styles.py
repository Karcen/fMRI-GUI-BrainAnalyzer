#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 主题样式 — Brain Analyzer v2.0"""
from PyQt5.QtCore import Qt

MONO = "Menlo, Monaco, 'Courier New', monospace"


class StyleManager:
    PRIMARY = "#0078d4"

    # ─── Light (纯黑白风 · 白底黑字 · 蓝/红仅用于强调与警告) ──────────────────
    def get_light_theme(self) -> str:
        return """
        /* ── Window & base ─── */
        QMainWindow { background: #ffffff; }
        QWidget      { background: #ffffff; color: #1a1a1a; font-size: 12px; }

        /* ── Left panel background ─── */
        QWidget#leftPanel { background: #ffffff; }

        /* ── Card-style GroupBox ─── */
        QGroupBox {
            background: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 6px;
            margin-top: 16px;
            padding: 10px 10px 8px 10px;
            font-size: 12px;
            font-weight: 600;
            color: #1a1a1a;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: -1px;
            padding: 0 6px;
            background: #ffffff;
            color: #1565C0;
            font-size: 12px;
            font-weight: 700;
        }

        /* ── Buttons — 黑白描边风 ─── */
        QPushButton {
            background: #ffffff;
            color: #1a1a1a;
            border: 1px solid #999999;
            border-radius: 6px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 600;
            min-height: 32px;
        }
        QPushButton:hover   { background: #f0f0f0; border-color: #1a1a1a; }
        QPushButton:pressed { background: #e0e0e0; }
        QPushButton:disabled { background: #f5f5f5; color: #aaaaaa; border-color: #dddddd; }

        /* ── Start button — 主操作用蓝色实心 ─── */
        QPushButton#startBtn {
            background: #1565C0;
            color: #ffffff;
            border: none;
            font-size: 14px;
            min-height: 46px;
            border-radius: 6px;
        }
        QPushButton#startBtn:hover   { background: #1976D2; }
        QPushButton#startBtn:pressed { background: #0D47A1; }
        QPushButton#startBtn:disabled { background: #f5f5f5; color: #aaaaaa; }

        /* ── Stop button — 危险操作用红色 ─── */
        QPushButton#stopBtn {
            background: #ffffff;
            color: #999999;
            border: 1px solid #dddddd;
        }
        QPushButton#stopBtn:enabled { background: #ffffff; color: #C62828; border: 1px solid #C62828; }
        QPushButton#stopBtn:hover   { background: #fdeaea; }

        /* ── Progress bar ─── */
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 4px;
            background: #f0f0f0;
            height: 10px;
            text-align: center;
            font-size: 10px;
            color: transparent;
        }
        QProgressBar::chunk { background: #1565C0; border-radius: 3px; }

        /* ── CheckBox ─── */
        QCheckBox {
            spacing: 6px;
            font-size: 12px;
            color: #1a1a1a;
        }
        QCheckBox:disabled { color: #aaaaaa; }

        /* ── RadioButton ─── */
        QRadioButton { spacing: 6px; font-size: 12px; color: #1a1a1a; }
        QRadioButton:disabled { color: #aaaaaa; }

        /* ── Label ─── */
        QLabel { font-size: 12px; color: #1a1a1a; background: transparent; }

        /* ── Log / Result text area — 白底黑字等宽 ─── */
        QTextEdit {
            background: #ffffff;
            color: #1a1a1a;
            border: 1px solid #cccccc;
            border-radius: 6px;
            font-family: """ + MONO + """;
            font-size: 12px;
            padding: 8px;
            selection-background-color: #bbdefb;
            selection-color: #1a1a1a;
        }

        /* ── Table (队列) ─── */
        QTableWidget {
            background: #ffffff;
            color: #1a1a1a;
            border: 1px solid #cccccc;
            border-radius: 6px;
            gridline-color: #e0e0e0;
            font-size: 12px;
        }
        QTableWidget::item:selected { background: #bbdefb; color: #1a1a1a; }
        QHeaderView::section {
            background: #f0f0f0;
            color: #1a1a1a;
            padding: 6px;
            border: none;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #cccccc;
            font-weight: 600;
        }

        /* ── Tabs ─── */
        QTabWidget::pane {
            border: 1px solid #cccccc;
            border-top: none;
            border-radius: 0 0 6px 6px;
        }
        QTabBar::tab {
            background: #f0f0f0;
            color: #666666;
            padding: 8px 20px;
            border: 1px solid #cccccc;
            border-bottom: none;
            border-radius: 6px 6px 0 0;
            margin-right: 2px;
            font-size: 12px;
        }
        QTabBar::tab:selected {
            background: #ffffff;
            color: #1565C0;
            font-weight: 700;
            border-bottom: 2px solid #ffffff;
        }
        QTabBar::tab:hover:!selected { background: #e5e5e5; }

        /* ── Scroll area / scrollbar ─── */
        QScrollArea { border: none; background: #ffffff; }
        QScrollBar:vertical {
            background: transparent;
            width: 8px;
            margin: 2px;
        }
        QScrollBar::handle:vertical {
            background: #bbbbbb;
            border-radius: 4px;
            min-height: 24px;
        }
        QScrollBar::handle:vertical:hover { background: #888888; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        /* ── ComboBox ─── */
        QComboBox {
            border: 1px solid #999999;
            border-radius: 6px;
            padding: 5px 10px;
            background: #ffffff;
            font-size: 12px;
            color: #1a1a1a;
        }
        QComboBox:hover { border-color: #1565C0; }
        QComboBox::drop-down { border: none; width: 24px; }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #1a1a1a;
            selection-background-color: #bbdefb;
            selection-color: #1a1a1a;
            border: 1px solid #cccccc;
        }

        /* ── Status bar ─── */
        QStatusBar { background: #f0f0f0; color: #666666; font-size: 11px; }
        QStatusBar::item { border: none; }

        /* ── Menu bar ─── */
        QMenuBar { background: #ffffff; color: #1a1a1a; border-bottom: 1px solid #cccccc; }
        QMenuBar::item { padding: 5px 10px; border-radius: 4px; background: transparent; }
        QMenuBar::item:selected { background: #1565C0; color: #ffffff; }
        QMenu { background: #ffffff; color: #1a1a1a; border: 1px solid #cccccc; }
        QMenu::item:selected { background: #1565C0; color: #ffffff; }

        /* ── Splitter ─── */
        QSplitter::handle { background: #cccccc; }
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
