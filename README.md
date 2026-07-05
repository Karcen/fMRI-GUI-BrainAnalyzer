# Brain Analyzer v2.0

**静息态 fMRI 脑网络一键自动化分析软件**  
Resting-State fMRI Brain Network Analysis — One-Click GUI

由 [Karcen Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **自动序列识别** | 加载包含多序列的 DICOM 文件夹，自动匹配 BOLD/T1/DWI 等序列 |
| **精确 DICOM 转换** | 调用 `dcm2niix` 正确解码 UIH 及主流厂商 mosaic 格式，获取 TR / SliceTiming |
| **完整预处理** | 丢弃前5TR → 切片时间校正（STC）→ PSC → 去趋势 → 带通滤波 0.01–0.1Hz → 6mm 平滑 |
| **质量控制** | DVARS、FD 代理、tSNR、高运动时间点统计，综合 QC 评分（0–100）|
| **功能连接 FC** | 33个 MNI 坐标 ROI（完全离线），8大脑网络 Pearson r 矩阵，PCC 种子连接 |
| **ALFF / fALFF** | 0.01–0.1 Hz FFT 幅值，z-score 归一化 |
| **ReHo** | Kendall's W 3×3×3 邻域（可选，约3分钟）|
| **图论分析** | networkx：聚类系数、全局/局部效率、小世界σ、模块化、Hub脑区 |
| **动态 FC** | 滑动窗口（88s）+ k-means 脑状态聚类 |
| **Brain Fingerprint** | FC 特征向量 + 综合摘要 |
| **交互式图表** | 10个 Plotly HTML 可视化 |
| **中文 PDF 报告** | 12章节完整报告（扫描参数、预处理、QC、FC、DMN、ALFF/ReHo、图论、动态FC、讨论）|
| **Word 报告** | 含所有图像的 .docx |
| **暗色模式** | Ctrl+D 切换 |

---

## 快速开始

### 要求

- macOS（已在 Apple Silicon 测试）
- [Anaconda Python](https://www.anaconda.com/) —— `/opt/anaconda3/bin/python`  
  含：PyQt5, nibabel, nilearn, networkx, scipy, scikit-learn, plotly, reportlab, python-docx, pydicom
- [dcm2niix](https://github.com/rordenlab/dcm2niix)：`brew install dcm2niix`

### 启动

```bash
/opt/anaconda3/bin/python /Users/karcenzheng/Downloads/BrainAnalyzer/BrainAnalyzer/launcher.py
```

或直接：

```bash
python launcher.py
```

### 使用流程

1. 点击 **"选择 DICOM 文件夹"** → 选择包含多序列的受试者根目录  
   （软件自动识别 BOLD 序列，支持 UIH / Siemens / GE / Philips）
2. 可选：自定义输出目录（默认在 DICOM 同级创建 `brain_analyzer_output/`）
3. 勾选所需分析选项（ReHo 可选，约额外3分钟）
4. 点击 **"▶ 开始分析"**
5. 完成后在输出目录查看：
   - `results/` — numpy 数组 + JSON 结果
   - `plots/` — 10个 Plotly 交互图表 HTML
   - `report_imgs/` — PNG 图像
   - `reports/` — PDF 及 Word 报告
   - `nifti/` — NIfTI 文件 + JSON sidecar

---

## 输出文件说明

```
brain_analyzer_output/
├── nifti/
│   ├── bold.nii.gz            # 原始 4D BOLD（dcm2niix 转换）
│   ├── bold.json              # 扫描参数 sidecar（含 SliceTiming）
│   └── preprocessed_bold.nii.gz
├── results/
│   ├── scan_parameters.json
│   ├── qc_metrics.json        # QC 评分、tSNR、DVARS、FD
│   ├── FC_pearson.npy         # 33×33 功能连接矩阵
│   ├── FC_fisherZ.npy
│   ├── roi_timeseries.npy     # 33×nt ROI 时间序列
│   ├── network_stats.json     # 8个脑网络统计
│   ├── ALFF_map.npy / fALFF_map.npy / ReHo_map.npy
│   ├── graph_metrics.json     # 图论指标
│   ├── dFC_results.json       # 动态FC
│   └── analysis_summary.json
├── plots/                     # Plotly 交互图表（HTML）
├── report_imgs/               # 报告图像（PNG）
└── reports/
    ├── fMRI_Report_<id>_zh.pdf
    └── fMRI_Report_<id>_zh.docx
```

---

## 预处理流程说明

| 步骤 | 方法 | 状态 |
|------|------|------|
| DICOM → NIfTI | dcm2niix v1.0.20250505 | ✅ |
| 丢弃前5TR | steady-state 稳定后采集 | ✅ |
| 切片时间校正 | 线性插值（参考时间 = TR/2）| ✅（有 SliceTiming 时）|
| 脑掩码 | 强度 65th 百分位 + 形态学运算 | ✅ |
| PSC 标准化 | (x-μ)/μ × 100 | ✅ |
| 线性去趋势 | OLS（截距+斜率）| ✅ |
| 带通滤波 | Butterworth 4阶 filtfilt，0.01–0.1 Hz | ✅ |
| 空间平滑 | Gaussian FWHM=6mm | ✅ |
| 头动矫正 | — | ⚠ 未执行（需 FSL/AFNI）|
| MNI 空间配准 | — | ⚠ 未执行（ROI 坐标近似映射）|
| ICA-AROMA | — | ⚠ 未执行（需 fMRIPrep）|

> 注：头动矫正未执行时，FD 代理使用全脑平均信号逐时点变化率估算（非六参数真实FD）。

---

## 已测试数据集

- **设备**：UIH uMR 790（3.0T），联影医疗
- **序列**：epi_bold_mww（64×64×33slice×240TR=480s），TR=2s，TE=30ms
- **DICOM 格式**：UIH SaveBySlc mosaic（384×384 px 存储 6×6=36 tiles/64×64）
- **结果**：QC 80/100，tSNR=25，SN FC=0.79，图论 σ=1.51

---

## 版本历史

| 版本 | 内容 |
|------|------|
| v2.0 | 完全重写引擎；dcm2niix 精确 mosaic 解码；STC；networkx 图论；完整 PDF 报告 |
| v1.0.7 | 修复 graph_theory_analysis 返回空字典导致的 KeyError |
| v1.0.6 | 自动识别 BOLD 序列；修复 UIH 无 ImagePositionPatient 标签问题 |
| v1.0.0 | 初始版本 |

---

## 免责声明

本软件生成的所有报告**仅供科研参考，不构成任何医学诊断**。  
非专业人士请勿依据报告判断大脑健康状态。如需临床评估，请咨询执照医学专业人员。
