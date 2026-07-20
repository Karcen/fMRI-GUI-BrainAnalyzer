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
    QTabWidget, QDialog, QComboBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from gui.styles import StyleManager
from gui.clinical_warning_dialog import ClinicalWarningDialog
from core.analyzer import BrainAnalyzer


class AnalysisWorker(QThread):
    """单人分析工作线程 — 调用 BrainAnalyzer.run_full_pipeline()

    支持两种输入：
      - DICOM 文件夹（input_type='dicom'，内置管线兜底）
      - fMRIPrep derivatives 目录（input_type='fmriprep'，金标准）
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, input_path, output_dir, options,
                 input_type="dicom", fmriprep_subject=None):
        super().__init__()
        self.input_path       = input_path
        self.output_dir       = output_dir
        self.options          = options
        self.input_type       = input_type
        self.fmriprep_subject = fmriprep_subject

    def run(self):
        try:
            def cb(pct, msg):
                self.progress.emit(pct, msg)

            self.progress.emit(1, "初始化分析引擎...")
            if self.input_type == "fmriprep":
                analyzer = BrainAnalyzer(
                    dicom_path=None, output_dir=self.output_dir,
                    progress_cb=cb, fmriprep_dir=self.input_path)
                analyzer.fmriprep_subject = self.fmriprep_subject
            else:
                analyzer = BrainAnalyzer(
                    self.input_path, self.output_dir, progress_cb=cb)
            results = analyzer.run_full_pipeline(self.options)
            self.finished.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(f"分析错误: {str(e)}\n\n{traceback.format_exc()}")


class CohortWorker(QThread):
    """队列分析工作线程 — 调用 CohortAnalyzer.run()（串行处理多受试者）"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, subjects, output_dir, options):
        super().__init__()
        self.subjects   = subjects
        self.output_dir = output_dir
        self.options    = options
        self._stop      = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            from core.cohort_analyzer import CohortAnalyzer
            def cb(pct, msg):
                self.progress.emit(pct, msg)
            ca = CohortAnalyzer(
                self.subjects, self.output_dir, self.options,
                progress_cb=cb, should_stop=lambda: self._stop)
            results = ca.run()
            self.finished.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(f"队列分析错误: {str(e)}\n\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dicom_path   = None
        self.output_dir   = None
        self.fmriprep_dir = None
        self.worker       = None
        self.cohort_worker= None
        self.cohort_subjects = []   # list[Subject]
        self.dark_mode    = False
        self.sm           = StyleManager()

        # 显示免责声明
        dlg = ClinicalWarningDialog(self)
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

        # 顶层模式切换：单人分析 / 队列分析
        self.mode_tabs = QTabWidget()

        # ── 单人分析 tab（左控制面板 + 右日志/结果）─────────────────────────
        single = QWidget(); single_lay = QVBoxLayout(single)
        single_lay.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 940])
        single_lay.addWidget(splitter, 1)
        self.mode_tabs.addTab(single, "🔬  单人分析")

        # ── 队列分析 tab ────────────────────────────────────────────────────
        self.mode_tabs.addTab(self._build_cohort_tab(), "👥  队列分析")

        root.addWidget(self.mode_tabs, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — 请选择 DICOM 文件夹 或 fMRIPrep 目录")

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
        self.lbl_dicom.setStyleSheet("color:#555; font-size:11px;")
        il.addWidget(self.lbl_dicom)
        b1 = QPushButton("选择 DICOM 文件夹 (Ctrl+O)")
        b1.clicked.connect(self._select_dicom)
        il.addWidget(b1)
        self.lbl_out = QLabel("输出: 自动创建于 DICOM 同级目录")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet("color:#555; font-size:11px;")
        il.addWidget(self.lbl_out)
        b2 = QPushButton("自定义输出目录")
        b2.clicked.connect(self._select_output)
        il.addWidget(b2)

        # fMRIPrep 金标准输入（可选）
        self.chk_use_fmriprep = QCheckBox("使用 fMRIPrep 预处理数据（金标准）")
        self.chk_use_fmriprep.setStyleSheet("font-size:11px; font-weight:bold; color:#1565C0;")
        self.chk_use_fmriprep.stateChanged.connect(self._toggle_fmriprep)
        il.addWidget(self.chk_use_fmriprep)
        self.btn_fmriprep = QPushButton("选择 fMRIPrep derivatives 目录")
        self.btn_fmriprep.setEnabled(False)
        self.btn_fmriprep.clicked.connect(self._select_fmriprep)
        il.addWidget(self.btn_fmriprep)
        self.lbl_fmriprep = QLabel("未选择 fMRIPrep 目录")
        self.lbl_fmriprep.setWordWrap(True)
        self.lbl_fmriprep.setStyleSheet("color:#555; font-size:10px;")
        il.addWidget(self.lbl_fmriprep)
        self.cmb_confound = QComboBox()
        self.cmb_confound.addItems([
            "24P  (24 运动参数)",
            "24P+aCompCor  (24 运动 + aCompCor)",
            "36P  (24 运动 + WM/CSF/GS + 导数平方)",
        ])
        self.cmb_confound.setEnabled(False)
        il.addWidget(self.cmb_confound)
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
        self.lbl_adv_hint.setStyleSheet("color:#555; font-size:10px;")
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
        self.lbl_mm_hint.setStyleSheet("color:#555; font-size:10px;")
        for c in [self.chk_t1, self.chk_dti, self.chk_qsm, self.lbl_mm_hint]:
            ml.addWidget(c)
        ol.addWidget(mg)

        # 报告
        rg = QGroupBox("报告生成")
        rl = QVBoxLayout(rg); rl.setSpacing(2)
        self.chk_pdf       = QCheckBox("PDF 报告");  self.chk_pdf.setChecked(True)
        self.chk_word      = QCheckBox("Word 报告"); self.chk_word.setChecked(True)
        self.chk_bilingual = QCheckBox("中英双语")
        self.chk_litupdate = QCheckBox("联网更新最新文献")
        self.chk_litupdate.setToolTip(
            "开启后，报告第十章「疾病脑网络文献对照」会从 PubMed 检索最近数年最新文献。\n"
            "仅发送疾病名+脑网络关键词，绝不发送任何受试者数据；离线时自动回退内置引用。")
        for c in [self.chk_pdf, self.chk_word, self.chk_bilingual, self.chk_litupdate]:
            rl.addWidget(c)
        _lit_hint = QLabel("联网仅检索「疾病+脑网络」关键词，不发送受试者数据")
        _lit_hint.setWordWrap(True)
        _lit_hint.setStyleSheet("color:#555; font-size:10px;")
        rl.addWidget(_lit_hint)
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
            ' style="color:#1565C0;text-decoration:none;">Jiacheng Zheng</a>'
            ' 使用 Claude Code 辅助开发')
        dev_lbl.setOpenExternalLinks(True)
        dev_lbl.setStyleSheet("font-size:10px; color:#555;")
        dev_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(dev_lbl)

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

    # ══ 队列分析 Tab ══════════════════════════════════════════════════════════

    def _build_cohort_tab(self) -> QWidget:
        """
        队列分析面板：
          左侧 — 受试者列表（表格）+ 添加/移除按钮 + 输出目录
          右侧 — 队列日志 + 组级结果摘要
        分析选项复用单人分析 Tab 的勾选状态（_collect_options）。
        """
        w = QWidget()
        outer = QHBoxLayout(w)
        splitter = QSplitter(Qt.Horizontal)

        # ── 左：受试者管理 ────────────────────────────────────────────────────
        left = QWidget(); left.setMinimumWidth(360)
        ll = QVBoxLayout(left); ll.setContentsMargins(6, 6, 6, 6); ll.setSpacing(6)

        info = QLabel("队列分析：串行处理多个受试者，自动汇总组级统计并导出 CSV。\n"
                      "分析选项沿用「单人分析」Tab 的勾选设置。")
        info.setWordWrap(True)
        info.setStyleSheet("color:#555; font-size:11px;")
        ll.addWidget(info)

        # 输入类型
        tg = QGroupBox("受试者输入类型")
        tl = QHBoxLayout(tg); tl.setSpacing(4)
        self.rb_cohort_dicom    = QRadioButton("DICOM 文件夹")
        self.rb_cohort_fmriprep = QRadioButton("fMRIPrep 目录（金标准）")
        self.rb_cohort_dicom.setChecked(True)
        self.cohort_type_grp = QButtonGroup(self)
        self.cohort_type_grp.addButton(self.rb_cohort_dicom)
        self.cohort_type_grp.addButton(self.rb_cohort_fmriprep)
        tl.addWidget(self.rb_cohort_dicom)
        tl.addWidget(self.rb_cohort_fmriprep)
        ll.addWidget(tg)

        # 受试者表格
        self.cohort_table = QTableWidget(0, 4)
        self.cohort_table.setHorizontalHeaderLabels(["受试者ID", "类型", "路径", "状态"])
        self.cohort_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.cohort_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cohort_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        ll.addWidget(self.cohort_table, 1)

        # 增删按钮
        btn_row = QHBoxLayout()
        b_add = QPushButton("＋ 添加受试者")
        b_add.clicked.connect(self._cohort_add_subject)
        b_addmany = QPushButton("批量添加（父目录）")
        b_addmany.clicked.connect(self._cohort_add_many)
        b_rm = QPushButton("－ 移除选中")
        b_rm.clicked.connect(self._cohort_remove_selected)
        for b in [b_add, b_addmany, b_rm]:
            btn_row.addWidget(b)
        ll.addLayout(btn_row)

        # 输出目录
        out_row = QHBoxLayout()
        self.lbl_cohort_out = QLabel("队列输出: 未选择")
        self.lbl_cohort_out.setWordWrap(True)
        self.lbl_cohort_out.setStyleSheet("color:#555; font-size:10px;")
        b_out = QPushButton("选择输出目录")
        b_out.clicked.connect(self._cohort_select_output)
        out_row.addWidget(self.lbl_cohort_out, 1)
        out_row.addWidget(b_out)
        ll.addLayout(out_row)

        # 开始/停止 + 进度
        self.btn_cohort_start = QPushButton("▶  开始队列分析")
        self.btn_cohort_start.setObjectName("startBtn")
        self.btn_cohort_start.setMinimumHeight(42)
        f = QFont(); f.setPointSize(12); f.setBold(True)
        self.btn_cohort_start.setFont(f)
        self.btn_cohort_start.clicked.connect(self._cohort_start)
        ll.addWidget(self.btn_cohort_start)

        self.btn_cohort_stop = QPushButton("■  停止队列")
        self.btn_cohort_stop.setObjectName("stopBtn")
        self.btn_cohort_stop.setEnabled(False)
        self.btn_cohort_stop.clicked.connect(self._cohort_stop)
        ll.addWidget(self.btn_cohort_stop)

        self.cohort_progress = QProgressBar()
        ll.addWidget(self.cohort_progress)

        splitter.addWidget(left)

        # ── 右：日志 + 组级结果 ───────────────────────────────────────────────
        right = QWidget(); rl = QVBoxLayout(right)
        self.cohort_tabs = QTabWidget()
        self.cohort_log = QTextEdit(); self.cohort_log.setReadOnly(True)
        self.cohort_log.setFont(QFont("Menlo", 10))
        self.cohort_tabs.addTab(self.cohort_log, "队列日志")
        self.cohort_result = QTextEdit(); self.cohort_result.setReadOnly(True)
        self.cohort_tabs.addTab(self.cohort_result, "组级结果")
        rl.addWidget(self.cohort_tabs)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([380, 900])
        outer.addWidget(splitter)

        # 队列运行时状态
        self.cohort_subjects = []   # list[(subject_id, input_type, path, fmriprep_subject)]
        self.cohort_worker   = None
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

    def _toggle_fmriprep(self, state):
        """勾选『使用 fMRIPrep 数据』时切换输入控件可用性。"""
        on = (state == Qt.Checked)
        self.btn_fmriprep.setEnabled(on)
        if hasattr(self, 'cmb_confound'):
            self.cmb_confound.setEnabled(on)

    def _select_fmriprep(self):
        folder = QFileDialog.getExistingDirectory(self, "选择 fMRIPrep derivatives 目录")
        if not folder:
            return
        # 校验是否为 fMRIPrep derivatives
        try:
            from core.fmriprep_loader import FMRIPrepLoader
            if not FMRIPrepLoader.looks_like_fmriprep(folder):
                QMessageBox.warning(self, "目录校验",
                    "该目录不像 fMRIPrep derivatives（未找到 sub-*/func 或 dataset_description.json）。\n"
                    "请选择 fMRIPrep 输出的 derivatives 根目录。")
                return
            loader = FMRIPrepLoader(folder)
            subs = loader.detect_subjects()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取 fMRIPrep 目录失败：{e}")
            return
        self.fmriprep_dir = folder
        self.lbl_fmriprep.setText(
            f"fMRIPrep: {folder}\n检测到 {len(subs)} 个受试者: {', '.join(subs[:5])}"
            + ("..." if len(subs) > 5 else ""))
        self._log(f"已选择 fMRIPrep 目录: {folder}（{len(subs)} 受试者）")
        if not self.output_dir:
            self.output_dir = os.path.join(os.path.dirname(folder), "brain_analyzer_output")
            self.lbl_out.setText(f"输出: {self.output_dir}")

    def _collect_options(self) -> dict:
        """收集当前 UI 上的所有分析选项（单人 / 队列共用）。"""
        return {
            'alff':      self.chk_alff.isChecked(),
            'reho':      self.chk_reho.isChecked(),
            'graph':     self.chk_graph.isChecked(),
            'dynamic':   self.chk_dynamic.isChecked(),
            'pdf':       self.chk_pdf.isChecked(),
            'word':      self.chk_word.isChecked(),
            'bilingual': self.chk_bilingual.isChecked(),
            'update_literature': self.chk_litupdate.isChecked(),
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
            # fMRIPrep
            'confound_strategy': self.cmb_confound.currentText().split()[0]
                                 if hasattr(self, 'cmb_confound') else '24P',
        }

    def _start(self):
        use_fp = getattr(self, 'chk_use_fmriprep', None) and self.chk_use_fmriprep.isChecked()
        if use_fp:
            if not self.fmriprep_dir:
                QMessageBox.warning(self, "警告", "请先选择 fMRIPrep derivatives 目录！"); return
            in_path, in_type = self.fmriprep_dir, "fmriprep"
        else:
            if not self.dicom_path:
                QMessageBox.warning(self, "警告", "请先选择 DICOM 文件夹！"); return
            in_path, in_type = self.dicom_path, "dicom"

        if not self.output_dir:
            parent = os.path.dirname(in_path)
            self.output_dir = os.path.join(parent, "brain_analyzer_output")
            self.lbl_out.setText(f"输出: {self.output_dir}")

        options = self._collect_options()
        self._log("=" * 60)
        self._log(f"开始多模态脑影像分析... [输入: {in_type}]")
        self._log(f"fMRI: ALFF={options['alff']} ReHo={options['reho']} Graph={options['graph']} dFC={options['dynamic']}")
        self._log(f"结构: T1={options['analyze_t1']} DTI={options['analyze_dti']} QSM={options['analyze_qsm']}")
        if in_type == "fmriprep":
            self._log(f"预处理: fMRIPrep 金标准  confound 策略={options['confound_strategy']}")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker = AnalysisWorker(in_path, self.output_dir, options,
                                     input_type=in_type)
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

    # ── 队列分析事件处理 ──────────────────────────────────────────────────────

    def _cohort_input_type(self) -> str:
        return "fmriprep" if self.rb_cohort_fmriprep.isChecked() else "dicom"

    def _cohort_add_subject(self):
        in_type = self._cohort_input_type()
        title = ("选择 fMRIPrep derivatives 目录" if in_type == "fmriprep"
                 else "选择受试者 DICOM 文件夹")
        folder = QFileDialog.getExistingDirectory(self, title)
        if not folder:
            return
        sid = os.path.basename(folder.rstrip("/")) or f"sub{len(self.cohort_subjects)+1}"
        # 去重
        if any(s[2] == folder for s in self.cohort_subjects):
            QMessageBox.information(self, "提示", "该路径已在队列中。")
            return
        self.cohort_subjects.append([sid, in_type, folder, None])
        self._cohort_refresh_table()
        self._cohort_log(f"添加受试者: {sid}  [{in_type}]  {folder}")

    def _cohort_add_many(self):
        """选择一个父目录，把其下每个子目录作为一个受试者加入。"""
        in_type = self._cohort_input_type()
        parent = QFileDialog.getExistingDirectory(self, "选择包含多个受试者的父目录")
        if not parent:
            return
        added = 0
        for name in sorted(os.listdir(parent)):
            sub = os.path.join(parent, name)
            if not os.path.isdir(sub):
                continue
            if any(s[2] == sub for s in self.cohort_subjects):
                continue
            self.cohort_subjects.append([name, in_type, sub, None])
            added += 1
        self._cohort_refresh_table()
        self._cohort_log(f"批量添加 {added} 个受试者（父目录: {parent}）")

    def _cohort_remove_selected(self):
        rows = sorted({idx.row() for idx in self.cohort_table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            if 0 <= r < len(self.cohort_subjects):
                self.cohort_subjects.pop(r)
        self._cohort_refresh_table()

    def _cohort_refresh_table(self):
        self.cohort_table.setRowCount(len(self.cohort_subjects))
        for r, (sid, in_type, path, status) in enumerate(self.cohort_subjects):
            self.cohort_table.setItem(r, 0, QTableWidgetItem(sid))
            self.cohort_table.setItem(r, 1, QTableWidgetItem(in_type))
            self.cohort_table.setItem(r, 2, QTableWidgetItem(path))
            self.cohort_table.setItem(r, 3, QTableWidgetItem(status or "pending"))

    def _cohort_select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择队列输出目录")
        if folder:
            self.cohort_output_dir = folder
            self.lbl_cohort_out.setText(f"队列输出: {folder}")

    def _cohort_start(self):
        if not self.cohort_subjects:
            QMessageBox.warning(self, "警告", "请先添加至少一个受试者！"); return
        if not getattr(self, "cohort_output_dir", None):
            QMessageBox.warning(self, "警告", "请先选择队列输出目录！"); return

        from core.cohort_analyzer import Subject
        subjects = []
        for sid, in_type, path, fp_sub in self.cohort_subjects:
            subjects.append(Subject(subject_id=sid, input_path=path,
                                    input_type=in_type, fmriprep_subject=fp_sub))

        options = self._collect_options()
        self._cohort_log("=" * 60)
        self._cohort_log(f"开始队列分析：{len(subjects)} 个受试者（串行）")
        self._cohort_log(f"输出目录: {self.cohort_output_dir}")

        self.btn_cohort_start.setEnabled(False)
        self.btn_cohort_stop.setEnabled(True)
        self.cohort_worker = CohortWorker(subjects, self.cohort_output_dir, options)
        self.cohort_worker.progress.connect(self._cohort_progress)
        self.cohort_worker.finished.connect(self._cohort_finished)
        self.cohort_worker.error.connect(self._cohort_error)
        self.cohort_worker.start()

    def _cohort_stop(self):
        if self.cohort_worker and self.cohort_worker.isRunning():
            self.cohort_worker.stop()
            self._cohort_log("\n[停止请求] 将在当前受试者完成后中止...")
            self.btn_cohort_stop.setEnabled(False)

    def _cohort_progress(self, value, message):
        self.cohort_progress.setValue(value)
        self._cohort_log(f"[{value:3d}%] {message}")
        self.status_bar.showMessage(message)

    def _cohort_finished(self, results):
        self.btn_cohort_start.setEnabled(True)
        self.btn_cohort_stop.setEnabled(False)
        # 回填每个受试者状态
        rows = {s["subject_id"]: s for s in results.get("subjects", [])}
        for entry in self.cohort_subjects:
            row = rows.get(entry[0])
            if row:
                entry[3] = row.get("status", "?")
        self._cohort_refresh_table()
        self._cohort_log("\n" + "=" * 60)
        self._cohort_log(f"✓ 队列完成：成功 {results.get('n_done',0)}，"
                         f"失败 {results.get('n_failed',0)}，共 {results.get('n_total',0)}")
        self.cohort_result.setHtml(self._build_cohort_summary(results))
        self.cohort_tabs.setCurrentIndex(1)
        QMessageBox.information(self, "队列完成",
            f"队列分析完成！\n成功 {results.get('n_done',0)} / {results.get('n_total',0)}\n"
            f"CSV: {results.get('csv','')}")

    def _cohort_error(self, msg):
        self.btn_cohort_start.setEnabled(True)
        self.btn_cohort_stop.setEnabled(False)
        self._cohort_log(f"\n[队列错误] {msg}")
        QMessageBox.critical(self, "队列错误",
            f"队列分析失败:\n{msg.splitlines()[0] if msg else msg}")

    def _cohort_log(self, msg):
        self.cohort_log.append(msg)

    def _build_cohort_summary(self, results) -> str:
        g = results.get("group", {})
        html = "<html><body style='font-family:Arial,sans-serif;font-size:13px;'>"
        html += "<h2>👥 队列组级结果</h2>"
        html += (f"<p><b>受试者:</b> 共 {results.get('n_total',0)}，"
                 f"成功 {results.get('n_done',0)}，失败 {results.get('n_failed',0)}</p>")
        n = g.get("n", 0)
        if n:
            html += f"<h3>组级统计 (n={n})</h3>"
            html += "<table border='1' cellspacing='0' cellpadding='4' " \
                    "style='border-collapse:collapse;'>"
            html += "<tr><th>指标</th><th>均值</th><th>标准差</th><th>范围</th></tr>"
            labels = {
                "QC_score": "QC 评分", "tSNR_median": "tSNR 中位数",
                "FD_proxy_pct_mean": "FD 均值", "DMN_internal_FC": "DMN 内部FC",
                "small_world_sigma": "小世界 σ", "global_efficiency": "全局效率",
            }
            for key, cn in labels.items():
                s = g.get(key)
                if isinstance(s, dict) and s.get("mean") is not None:
                    html += (f"<tr><td>{cn}</td><td>{s.get('mean','')}</td>"
                             f"<td>{s.get('std','')}</td>"
                             f"<td>{s.get('min','')} – {s.get('max','')}</td></tr>")
            html += "</table>"
        csv = results.get("csv", "")
        if csv:
            html += f"<p><b>📄 CSV 汇总:</b> {csv}</p>"
        html += "</body></html>"
        return html

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
<p>由 <a href="https://karcen.github.io/zhengjiacheng.github.io/">Jiacheng Zheng</a>
使用 Claude Code 辅助开发</p>""")

