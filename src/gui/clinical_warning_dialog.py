#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临床级启动警告对话框
严格声明：仅限医学专业人员使用，不作临床诊断
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QScrollArea, QWidget, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor


class ClinicalWarningDialog(QDialog):
    """
    三步勾选式临床警告 — 全部勾选才能进入软件。
    替换原 DisclaimerDialog。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠ 使用限制声明 — Brain Analyzer")
        self.setMinimumSize(680, 560)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowCloseButtonHint)   # 禁用右上角 ×
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        # ── 红色警告标题栏 ────────────────────────────────────────────────────
        banner = QFrame()
        banner.setStyleSheet(
            "background:#c62828; border-radius:8px; padding:4px;")
        bl = QVBoxLayout(banner); bl.setContentsMargins(16, 10, 16, 10)

        t1 = QLabel("🚫  严禁非医学相关人员使用")
        t1.setStyleSheet("color:white; font-size:18px; font-weight:800;")
        t1.setAlignment(Qt.AlignCenter)
        bl.addWidget(t1)

        t2 = QLabel("NON-MEDICAL PERSONNEL MUST NOT USE THIS SOFTWARE")
        t2.setStyleSheet("color:#ffcdd2; font-size:11px; font-weight:600;")
        t2.setAlignment(Qt.AlignCenter)
        bl.addWidget(t2)

        root.addWidget(banner)

        # ── 正文滚动区 ────────────────────────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        il = QVBoxLayout(inner); il.setSpacing(8)

        body_html = """
<p style="font-size:13px; color:#b71c1c; font-weight:700;">
【适用人员范围 / Authorized Users Only】
</p>
<p style="font-size:12px; line-height:1.7;">
本软件（Brain Analyzer）为<b>科研级静息态 fMRI 脑网络分析平台</b>，
仅供以下专业人员在科研场景中使用：
</p>
<ul style="font-size:12px; line-height:1.8;">
  <li>执业医师或注册医师（神经科 / 精神科 / 影像科）</li>
  <li>经过神经影像培训的医学研究员</li>
  <li>在导师指导下开展研究的医学院学生</li>
  <li>经所在机构正式授权的其他医疗卫生专业人员</li>
</ul>

<p style="font-size:13px; color:#b71c1c; font-weight:700; margin-top:10px;">
【严重警告 / CRITICAL WARNING】
</p>
<ul style="font-size:12px; line-height:1.8;">
  <li>本软件生成的全部结果（FC矩阵、ALFF/ReHo图谱、疾病文献对照等）
      <b>均属探索性科研分析，绝对不构成临床诊断依据</b>。</li>
  <li>任何人不得将本软件结果直接用于患者诊疗决策、疾病诊断或治疗方案制定。</li>
  <li>单受试者神经影像数据不具备群体统计推断意义，
      个体脑网络变异极大，正常变异范围宽泛。</li>
  <li>本软件预处理管线与临床金标准（fMRIPrep + FSL + ANTs）存在差异，
      需审慎解读分析结果。</li>
  <li>如有临床健康疑虑，请立即咨询执照神经科或精神科医生。</li>
</ul>

<p style="font-size:12px; color:#555; margin-top:8px;">
<b>Research Use Only — English:</b><br>
This software is strictly for <i>research purposes only</i> by qualified medical
and research professionals. Results do NOT constitute medical diagnosis,
clinical recommendations, or treatment guidance. Never use analysis
outputs for direct patient care decisions. Consult a licensed clinician
for any health concerns.
</p>
<p style="font-size:11px; color:#888; margin-top:4px;">
由 <a href="https://karcen.github.io/zhengjiacheng.github.io/">Jiacheng Zheng</a> 使用 Claude Code 辅助开发 · © 2026 NeuroLab
</p>
"""
        body = QLabel(body_html)
        body.setWordWrap(True)
        body.setOpenExternalLinks(True)
        body.setTextFormat(Qt.RichText)
        il.addWidget(body)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── 分隔线 ────────────────────────────────────────────────────────────
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#e0e0e0;"); root.addWidget(line)

        # ── 三条声明勾选框 ────────────────────────────────────────────────────
        chk_frame = QWidget()
        chk_frame.setStyleSheet(
            "background:#fff8e1; border:1px solid #ffe082; border-radius:6px;")
        cf_lay = QVBoxLayout(chk_frame); cf_lay.setContentsMargins(14, 10, 14, 10)

        note = QLabel("⚠ 请仔细阅读以上声明，全部勾选后方可使用本软件：")
        note.setStyleSheet("font-weight:700; font-size:12px; color:#e65100;")
        cf_lay.addWidget(note)

        self._checks = []
        declarations = [
            "我确认本人为医疗卫生专业人员（执业医师 / 医学研究员 / 医学院学生），"
            "且在合法授权的科研项目中使用本软件。",
            "我理解本软件分析结果仅供科研参考，"
            "不作为临床诊断、疾病确认或治疗建议的依据，"
            "且本人不会将结果直接用于患者诊疗决策。",
            "我已阅读并完全理解上述使用限制声明，同意承担违规使用的全部责任。",
        ]
        for txt in declarations:
            cb = QCheckBox()
            cb.setStyleSheet("font-size:12px; padding:3px 0;")
            cb.stateChanged.connect(self._refresh_btn)
            lbl = QLabel(txt)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:12px; padding:3px 0; color:#333; background:transparent;")
            # 点击文字也可勾选
            lbl.mousePressEvent = lambda e, c=cb: c.toggle()
            row = QHBoxLayout()
            row.addWidget(cb, 0, Qt.AlignTop)
            row.addWidget(lbl, 1)
            cf_lay.addLayout(row)
            self._checks.append(cb)

        root.addWidget(chk_frame)

        # ── 按钮行 ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.exit_btn = QPushButton("不同意 — 退出程序")
        self.exit_btn.setMinimumHeight(38)
        self.exit_btn.setStyleSheet(
            "background:#e53935; color:white; border-radius:6px; font-size:12px;")
        self.exit_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("✓  我已理解并同意，进入软件")
        self.ok_btn.setMinimumHeight(38)
        self.ok_btn.setEnabled(False)
        self.ok_btn.setStyleSheet(
            "background:#1b5e20; color:white; border-radius:6px; "
            "font-size:13px; font-weight:700;")
        self.ok_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.exit_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.ok_btn)
        root.addLayout(btn_row)

    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_btn(self):
        all_checked = all(c.isChecked() for c in self._checks)
        self.ok_btn.setEnabled(all_checked)
        if all_checked:
            self.ok_btn.setStyleSheet(
                "background:#2e7d32; color:white; border-radius:6px; "
                "font-size:13px; font-weight:700;")
        else:
            self.ok_btn.setStyleSheet(
                "background:#555; color:#aaa; border-radius:6px; "
                "font-size:13px;")
