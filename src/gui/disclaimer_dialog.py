#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动免责声明对话框"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QScrollArea, QWidget)
from PyQt5.QtCore import Qt

class DisclaimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用须知 — Brain Analyzer")
        self.setMinimumSize(620, 460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("⚠ 使用须知 / Disclaimer")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#1565C0;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        text = QLabel("""
<b>【非专业人士须知】</b><br>
本软件（Brain Analyzer）为科研级静息态 fMRI 脑网络分析工具，由
<a href="https://karcen.github.io/zhengjiacheng.github.io/">Karcen Zheng</a>
使用 Claude Code 辅助开发。<br><br>

<b>重要声明：</b><br>
1. 本软件生成的所有分析结果，包括脑网络指标、功能连接矩阵、ALFF/ReHo 图谱及报告内容，
   <b>均属探索性科研分析</b>，不构成任何形式的医学诊断、疾病确认或治疗建议。<br><br>
2. <b>非专业人士请勿</b>依据本报告自行判断大脑健康状态或疾病风险。
   个体脑网络差异极大，正常变异范围宽泛，单受试者数据不具备统计学推断意义。<br><br>
3. 如需临床评估，请咨询有执照的神经科或精神科医学专业人员。<br><br>
4. 本软件数据处理流程尚未进行完整的头动矫正与 MNI 空间配准，
   分析结果与金标准 fMRIPrep 流程存在差异，结果需审慎解读。<br><br>

<b>Disclaimer (English):</b><br>
This software is for <i>research purposes only</i>. Results do not constitute
medical diagnosis or clinical advice. If you have health concerns,
please consult a licensed medical professional.<br><br>

<b>由 Karcen Zheng 使用 Claude Code 辅助开发</b><br>
© 2026 NeuroLab
""")
        text.setWordWrap(True)
        text.setOpenExternalLinks(True)
        text.setTextFormat(Qt.RichText)
        text.setStyleSheet("font-size:12px; padding:8px;")
        inner_layout.addWidget(text)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self.agree_cb = QCheckBox("我已阅读并理解上述使用须知，同意继续使用本软件")
        self.agree_cb.setStyleSheet("font-size:13px; font-weight:bold;")
        self.agree_cb.stateChanged.connect(self._on_agree)
        layout.addWidget(self.agree_cb)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("同意并继续")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setMinimumHeight(36)
        self.ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("不同意，退出")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background:#e53935;")
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def _on_agree(self, state):
        self.ok_btn.setEnabled(state == Qt.Checked)
