#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI 主窗口 — Brain Analyzer v2.0
"""
import os, sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QProgressBar,
    QFileDialog, QGroupBox, QCheckBox, QSplitter,
    QStatusBar, QAction, QMenuBar, QMessageBox,
    QTabWidget, QDialog, QComboBox, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from gui.styles import StyleManager
from gui.disclaimer_dialog import DisclaimerDialog
from core.analyzer import BrainAnalyzer


class AnalysisWorker(QThread):
    """分析工作线程 — 调用 BrainAnalyzer.run_full_pipeline()"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, dicom_path, output_dir, options):
        super().__init__()
        self.dicom_path = dicom_path
        self.output_dir = output_dir
        self.options    = options

    def run(self):
        try:
            def cb(pct, msg):
                self.progress.emit(pct, msg)

            self.progress.emit(1, "初始化分析引擎...")
            analyzer = BrainAnalyzer(
                self.dicom_path, self.output_dir, progress_cb=cb)
            results = analyzer.run_full_pipeline(self.options)
            self.finished.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(f"分析错误: {str(e)}\n\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dicom_path = None
        self.output_dir = None
        self.worker     = None
        self.dark_mode  = False
        self.sm         = StyleManager()

        # 显示免责声明
        dlg = DisclaimerDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)

        self._init_ui()
        self._apply_theme()

    # ── UI 构建 ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("Brain Analyzer v2.0 — 脑影像自动分析软件")
        self.setGeometry(100, 100, 1280, 820)
        self._create_menu()

        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 主内容：左控制面板 + 右日志/结果  (splitter 填满窗口)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 940])
        root.addWidget(splitter, 1)   # stretch=1 → 填满全部可用高度

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — 请选择 DICOM 文件夹")

    def _create_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu('文件')
        for label, shortcut, slot in [
            ('打开 DICOM 文件夹', 'Ctrl+O', self._select_dicom),
            ('选择输出目录',      '',        self._select_output),
            ('退出',              'Ctrl+Q',  self.close),
        ]:
            a = QAction(label, self)
            if shortcut: a.setShortcut(shortcut)
            a.triggered.connect(slot); fm.addAction(a)
            if label == '选择输出目录': fm.addSeparator()

        vm = mb.addMenu('视图')
        ta = QAction('切换深色模式', self); ta.setShortcut('Ctrl+D')
        ta.triggered.connect(self._toggle_theme); vm.addAction(ta)

        hm = mb.addMenu('帮助')
        aa = QAction('关于', self); aa.triggered.connect(self._about); hm.addAction(aa)

    def _build_left(self) -> QWidget:
        """
        三段式左侧面板：
          ① 顶部（固定）— DICOM 输入 + 输出路径
          ② 中部（可滚动）— 所有分析选项
          ③ 底部（固定）— 开始/停止按钮 + 进度条 + 开发者信息
        """
        w = QWidget()
        w.setMinimumWidth(300)
        w.setMaximumWidth(400)
        root = QVBoxLayout(w)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ══ ① 顶部：输入区（固定，始终可见）════════════════════════════════
        ig = QGroupBox("📂 输入")
        il = QVBoxLayout(ig); il.setSpacing(4)
        self.lbl_dicom = QLabel("未选择 DICOM 文件夹")
        self.lbl_dicom.setWordWrap(True)
        self.lbl_dicom.setStyleSheet("color:#888; font-size:11px;")
        il.addWidget(self.lbl_dicom)
        b1 = QPushButton("选择 DICOM 文件夹 (Ctrl+O)")
        b1.clicked.connect(self._select_dicom)
        il.addWidget(b1)
        self.lbl_out = QLabel("输出: 自动创建于 DICOM 同级目录")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet("color:#888; font-size:11px;")
        il.addWidget(self.lbl_out)
        b2 = QPushButton("自定义输出目录")
        b2.clicked.connect(self._select_output)
        il.addWidget(b2)
        root.addWidget(ig)

        # ══ ② 中部：选项区（QScrollArea，可折叠滚动）════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(scroll.NoFrame)
        opts = QWidget()
        ol = QVBoxLayout(opts); ol.setSpacing(4); ol.setContentsMargins(0,0,2,0)

        # fMRI 分析
        ag = QGroupBox("fMRI 分析选项")
        al = QVBoxLayout(ag); al.setSpacing(2)
        self.chk_alff    = QCheckBox("ALFF / fALFF");       self.chk_alff.setChecked(True)
        self.chk_reho    = QCheckBox("ReHo（~3 分钟）");    self.chk_reho.setChecked(True)
        self.chk_graph   = QCheckBox("图论分析");            self.chk_graph.setChecked(True)
        self.chk_dynamic = QCheckBox("动态功能连接");        self.chk_dynamic.setChecked(True)
        for c in [self.chk_alff, self.chk_reho, self.chk_graph, self.chk_dynamic]:
            al.addWidget(c)
        ol.addWidget(ag)

        # 高级预处理
        adv_g = QGroupBox("高级预处理 (Scientific Grade)")
        adv_l = QVBoxLayout(adv_g); adv_l.setSpacing(2)
        self.chk_motion   = QCheckBox("运动估计（相位相关 → 真实 FD）")
        self.chk_motion.setChecked(True)
        self.chk_nuisance = QCheckBox("Nuisance Regression")
        self.chk_nuisance.setChecked(True)
        self.chk_motion24 = QCheckBox("  └ 24 参数运动模型（默认 6）")
        self.chk_wm_csf   = QCheckBox("  └ WM / CSF 回归")
        self.chk_wm_csf.setChecked(True)
        self.chk_gsr      = QCheckBox("  └ 全局信号回归 GSR（默认关闭）")
        self.chk_carpet   = QCheckBox("Carpet Plot + Scrubbing 建议")
        self.chk_carpet.setChecked(True)
        self.chk_schaefer = QCheckBox("Schaefer-2018 Atlas FC（需联网）")
        self.cmb_schaefer = QComboBox()
        self.cmb_schaefer.addItems(["100 parcels", "200 parcels", "400 parcels"])
        self.cmb_schaefer.setEnabled(False)
        self.chk_schaefer.stateChanged.connect(
            lambda s: self.cmb_schaefer.setEnabled(s == Qt.Checked))
        self.lbl_adv_hint = QLabel("☝ 运动估计 +10s；Schaefer 需首次联网")
        self.lbl_adv_hint.setStyleSheet("color:#888; font-size:10px;")
        for w2 in [self.chk_motion, self.chk_nuisance, self.chk_motion24,
                   self.chk_wm_csf, self.chk_gsr, self.chk_carpet,
                   self.chk_schaefer, self.cmb_schaefer, self.lbl_adv_hint]:
            adv_l.addWidget(w2)
        ol.addWidget(adv_g)

        # 多模态
        mg = QGroupBox("多模态分析（自动识别序列）")
        ml = QVBoxLayout(mg); ml.setSpacing(2)
        self.chk_t1  = QCheckBox("T1 结构像（体积 / 分割）"); self.chk_t1.setChecked(True)
        self.chk_dti = QCheckBox("DTI（FA / MD / WM 束）");   self.chk_dti.setChecked(True)
        self.chk_qsm = QCheckBox("QSM 铁沉积分析");           self.chk_qsm.setChecked(True)
        self.lbl_mm_hint = QLabel("☝ 无对应序列时自动跳过")
        self.lbl_mm_hint.setStyleSheet("color:#888; font-size:10px;")
        for c in [self.chk_t1, self.chk_dti, self.chk_qsm, self.lbl_mm_hint]:
            ml.addWidget(c)
        ol.addWidget(mg)

        # 报告
        rg = QGroupBox("报告生成")
        rl = QVBoxLayout(rg); rl.setSpacing(2)
        self.chk_pdf       = QCheckBox("PDF 报告");  self.chk_pdf.setChecked(True)
        self.chk_word      = QCheckBox("Word 报告"); self.chk_word.setChecked(True)
        self.chk_bilingual = QCheckBox("中英双语")
        for c in [self.chk_pdf, self.chk_word, self.chk_bilingual]:
            rl.addWidget(c)
        ol.addWidget(rg)
        ol.addStretch()

        scroll.setWidget(opts)
        root.addWidget(scroll, 1)   # stretch=1 → 占据中部剩余空间

        # ══ ③ 底部：按钮 + 进度条 + 署名（固定，始终可见）══════════════════
        self.btn_start = QPushButton("▶  开 始 分 析")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.setMinimumHeight(46)
        f = QFont(); f.setPointSize(12); f.setBold(True)
        self.btn_start.setFont(f)
        self.btn_start.clicked.connect(self._start)
        root.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  停止")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        root.addWidget(self.btn_stop)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        root.addWidget(self.progress)

        # 开发者署名移到左侧底部
        dev_lbl = QLabel(
            '由 <a href="https://karcen.github.io/zhengjiacheng.github.io/"'
            ' style="color:#0078d4;text-decoration:none;">Karcen Zheng</a>'
            ' 使用 Claude Code 辅助开发')
        dev_lbl.setOpenExternalLinks(True)
        dev_lbl.setStyleSheet("font-size:10px; color:#aaa;")
        dev_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(dev_lbl)

        return w
        return w

    def _build_right(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        self.tabs = QTabWidget()

        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.tabs.addTab(self.log_text, "分析日志")

        self.result_text = QTextEdit(); self.result_text.setReadOnly(True)
        self.tabs.addTab(self.result_text, "分析结果")

        lay.addWidget(self.tabs)
        return w

    # ── 事件处理 ─────────────────────────────────────────────────────────────

    def _select_dicom(self):
        folder = QFileDialog.getExistingDirectory(self, "选择 DICOM 文件夹")
        if folder:
            self.dicom_path = folder
            self.lbl_dicom.setText(f"DICOM: {folder}")
            self._log(f"已选择: {folder}")
            if not self.output_dir:
                parent = os.path.dirname(folder)
                self.output_dir = os.path.join(parent, "brain_analyzer_output")
                self.lbl_out.setText(f"输出: {self.output_dir}")

    def _select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.output_dir = folder
            self.lbl_out.setText(f"输出: {folder}")

    def _start(self):
        if not self.dicom_path:
            QMessageBox.warning(self, "警告", "请先选择 DICOM 文件夹！"); return

        options = {
            'alff':      self.chk_alff.isChecked(),
            'reho':      self.chk_reho.isChecked(),
            'graph':     self.chk_graph.isChecked(),
            'dynamic':   self.chk_dynamic.isChecked(),
            'pdf':       self.chk_pdf.isChecked(),
            'word':      self.chk_word.isChecked(),
            'bilingual': self.chk_bilingual.isChecked(),
            # 多模态选项
            'analyze_t1':  self.chk_t1.isChecked(),
            'analyze_dti': self.chk_dti.isChecked(),
            'analyze_qsm': self.chk_qsm.isChecked(),
            # 高级预处理
            'motion_correction':    self.chk_motion.isChecked(),
            'nuisance_regression':  self.chk_nuisance.isChecked(),
            'motion_24':            self.chk_motion24.isChecked(),
            'wm_csf':               self.chk_wm_csf.isChecked(),
            'gsr':                  self.chk_gsr.isChecked(),
            'carpet_plot':          self.chk_carpet.isChecked(),
            'schaefer':             self.chk_schaefer.isChecked(),
            'schaefer_n': int(self.cmb_schaefer.currentText().split()[0]),
        }
        self._log("=" * 60)
        self._log("开始多模态脑影像分析...")
        self._log(f"fMRI: ALFF={options['alff']} ReHo={options['reho']} Graph={options['graph']} dFC={options['dynamic']}")
        self._log(f"结构: T1={options['analyze_t1']} DTI={options['analyze_dti']} QSM={options['analyze_qsm']}")

        self.worker = AnalysisWorker(self.dicom_path, self.output_dir, options)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate(); self.worker.wait()
            self._log("\n[已停止] 用户取消分析")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_bar.showMessage("已停止")

    def _update_progress(self, value, message):
        self.progress.setValue(value)
        self._log(f"[{value:3d}%] {message}")
        self.status_bar.showMessage(message)

    def _on_finished(self, results):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._log("\n" + "=" * 60)
        self._log("✓ 分析完成！")
        self._log("=" * 60)
        self.result_text.setHtml(self._build_summary(results))
        self.tabs.setCurrentIndex(1)
        QMessageBox.information(self, "完成",
            f"分析完成！\n结果已保存至:\n{self.output_dir}")
        self.status_bar.showMessage("分析完成")

    def _on_error(self, msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._log(f"\n[错误] {msg}")
        # 只显示第一行（简洁）
        QMessageBox.critical(self, "错误",
            f"分析失败:\n{msg.splitlines()[0] if msg else msg}")
        self.status_bar.showMessage("分析失败")

    # ── 辅助 ─────────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_text.append(msg)

    def _build_summary(self, results) -> str:
        html = "<html><body style='font-family: Arial, sans-serif; font-size:13px;'>"
        html += "<h2>🧠 分析结果摘要</h2>"

        sp = results.get("scan_params", {})
        if sp:
            html += "<h3>📋 扫描参数</h3><ul>"
            html += f"<li><b>受试者ID:</b> {sp.get('subject_id','N/A')}</li>"
            html += f"<li><b>TR:</b> {sp.get('TR','N/A')} s</li>"
            html += f"<li><b>扫描仪:</b> {sp.get('scanner','N/A')}</li>"
            html += f"<li><b>STC:</b> {'✓ 已执行' if sp.get('slice_timing_available') else '⚠ 无SliceTiming'}</li>"
            html += "</ul>"

        qc = results.get("qc_metrics", {})
        if qc:
            score = qc.get("QC_score", 0)
            stars = qc.get("QC_stars", "")
            color = "#27ae60" if score >= 80 else ("#f39c12" if score >= 60 else "#e74c3c")
            html += f"<h3>✅ 质量控制</h3><ul>"
            html += f"<li><b>QC评分:</b> <span style='color:{color};font-weight:bold;'>{score}/100 {stars}</span></li>"
            html += f"<li><b>tSNR中位数:</b> {qc.get('tSNR_median',0):.1f}</li>"
            html += f"<li><b>高运动TP:</b> {qc.get('pct_bad_TPs',0):.1f}%</li>"
            html += f"<li><b>时间点数:</b> {qc.get('n_timepoints',0)}</li>"
            html += "</ul>"

        fc = results.get("fc", {})
        if fc:
            html += "<h3>🔗 功能连接</h3><ul>"
            html += f"<li><b>DMN 内部FC:</b> r = {fc.get('dmn_mean_fc',0):.3f}</li>"
            ns = fc.get("network_stats", {})
            for net, v in list(ns.items())[:4]:
                html += f"<li><b>{net}:</b> {v['mean_FC']:.3f}</li>"
            html += "</ul>"

        graph = results.get("graph", {})
        if graph:
            hubs = graph.get("hub_regions", [])
            html += "<h3>🕸 图论分析</h3><ul>"
            html += f"<li><b>聚类系数CC:</b> {graph.get('avg_clustering',0):.3f}</li>"
            html += f"<li><b>全局效率GE:</b> {graph.get('global_efficiency',0):.3f}</li>"
            html += f"<li><b>小世界σ:</b> {graph.get('small_world_sigma',0):.2f}</li>"
            html += f"<li><b>Hub脑区:</b> {', '.join(hubs) if hubs else '—'}</li>"
            html += "</ul>"

        # 报告文件
        html += "<h3>📁 生成文件</h3><ul>"
        plots = results.get("plots", [])
        if plots:
            html += f"<li><b>交互图表:</b> {len(plots)} 个 HTML</li>"
        imgs = results.get("report_images", [])
        if imgs:
            html += f"<li><b>报告图像:</b> {len(imgs)} 张 PNG</li>"
        reports = results.get("reports", {})
        for key, path in reports.items():
            html += f"<li><b>{key.upper()}:</b> {os.path.basename(path)}</li>"
        html += "</ul>"
        html += f"<p><i>📂 全部文件保存在: {self.output_dir}</i></p>"
        html += "</body></html>"
        return html

    # ── 主题 / 菜单 ──────────────────────────────────────────────────────────

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(self.sm.get_dark_theme() if self.dark_mode
                           else self.sm.get_light_theme())

    def _about(self):
        QMessageBox.about(self, "关于 Brain Analyzer",
            """<h2>Brain Analyzer v2.0</h2>
<p><b>静息态fMRI脑网络自动化分析软件</b></p>
<p>✓ UIH 及主流 MRI 厂商 DICOM 自动识别<br>
✓ dcm2niix 精确解码（含 mosaic 格式）<br>
✓ 完整预处理：STC + 带通滤波 + 空间平滑<br>
✓ 功能连接、ALFF/fALFF/ReHo、图论、动态FC<br>
✓ 中文 PDF + Word 双语报告<br>
✓ 交互式 Plotly HTML 图表</p>
<hr>
<p>由 <a href="https://karcen.github.io/zhengjiacheng.github.io/">Karcen Zheng</a>
使用 Claude Code 辅助开发</p>""")

