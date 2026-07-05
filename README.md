# Brain Analyzer v2.0

<div align="center">

**静息态 fMRI 多模态脑影像一键自动化分析平台**

*Resting-State fMRI Multi-Modal Brain Imaging Analysis Platform*

由 [Karcen Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)](https://pypi.org/project/PyQt5/)
[![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey)](https://www.apple.com/macos/)
[![License](https://img.shields.io/badge/License-Research%20Only-orange)](#免责声明)

</div>

---

## 目录

- [简介](#简介)
- [功能概览](#功能概览)
- [安装依赖](#安装依赖)
- [快速开始](#快速开始)
- [分析流程详解](#分析流程详解)
- [输出文件说明](#输出文件说明)
- [已测试设备与数据](#已测试设备与数据)
- [版本历史](#版本历史)
- [免责声明](#免责声明)

---

## 简介

Brain Analyzer v2.0 是一款面向神经科学研究者的**一键式静息态 fMRI 分析 GUI 软件**。

只需选择一个包含多序列的 DICOM 文件夹，软件将**自动识别 BOLD、T1、DTI、QSM 等序列**，依次完成从 DICOM 转换、预处理、功能连接分析，到 PDF/Word 报告生成的完整流程。

**核心设计理念：**
- 🧠 零配置，一键运行
- 📦 完全离线（atlas 无需翻墙下载）
- 🔬 算法与科研级管线对标
- 📝 自动生成中英文双语报告

---

## 功能概览

### fMRI 静息态分析

| 模块 | 方法 | 说明 |
|------|------|------|
| DICOM → NIfTI | `dcm2niix v1.0.20250505` | 正确解码 UIH 等厂商 Mosaic 格式，自动提取 TR / SliceTiming |
| 切片时间校正 | 线性插值 STC | 参考时间 = TR/2，利用 JSON sidecar |
| 运动估计 | 相位相关法（3D 平移）| 纯 Python 实现，生成真实 FD(mm) |
| Nuisance Regression | OLS，6/24 参数 | 运动参数 + WM/CSF 回归 + 可选全局信号 |
| 带通滤波 | Butterworth 4 阶 filtfilt | 0.01–0.1 Hz |
| 空间平滑 | Gaussian FWHM=6mm | |
| QC 质控 | DVARS / FD / tSNR | Carpet Plot + Scrubbing 建议 |
| 功能连接 FC | Pearson r + Fisher-Z | 33 MNI-coord ROI（离线）/ Schaefer-2018（需联网） |
| ALFF / fALFF | FFT 幅值 0.01–0.1 Hz | z-score 归一化 |
| ReHo | Kendall's W 3×3×3 邻域 | 可选，约 3 分钟 |
| 图论分析 | NetworkX | CC / GE / LE / σ / Q / Hub 脑区 |
| 动态功能连接 | 滑动窗口 88s + K-means | 脑状态聚类，占比与转换次数 |

### 多模态分析

| 序列 | 分析内容 |
|------|---------|
| **T1 结构像** | 脑掩码 + GMM 3 类组织分割 + GM/WM/CSF 体积 + 半球对称性 |
| **DTI 弥散** | OLS 张量拟合 → FA/MD/AD/RD 图谱 + 13 条主要 WM 束 ROI 统计 |
| **QSM 铁沉积** | 14 个深部灰质 ROI 磁化率值 + 文献参考值对比 |

### 报告

- **中文 PDF**：15 章节，含扫描参数、预处理、QC、FC 矩阵、DMN、ALFF/ReHo、图论、动态FC、T1、DTI、QSM、10 种疾病文献对照、神经科学讨论
- **英文 PDF**：完整英文版，结构与中文版相同
- **Word (.docx)**：含所有分析图像，可二次编辑

---

## 安装依赖

### 系统要求

- macOS（Apple Silicon 或 Intel，推荐 macOS 14+）
- [Anaconda Python 3.13](https://www.anaconda.com/download)
- [dcm2niix](https://github.com/rordenlab/dcm2niix)：`brew install dcm2niix`

### Python 包

使用 Anaconda 自带的包，无需额外安装大多数依赖：

```bash
# 验证关键包是否存在
/opt/anaconda3/bin/python -c "
import PyQt5, nibabel, nilearn, networkx, sklearn, scipy, plotly, reportlab, docx, pydicom
print('✓ All dependencies OK')
"
```

如缺少某个包：

```bash
/opt/anaconda3/bin/pip install pyqt5 nibabel nilearn networkx \
    scikit-learn scipy plotly reportlab python-docx pydicom
```

---

## 快速开始

### 启动软件

```bash
/opt/anaconda3/bin/python \
  /Users/karcenzheng/Downloads/BrainAnalyzer/BrainAnalyzer/launcher.py
```

或者直接：

```bash
cd /Users/karcenzheng/Downloads/BrainAnalyzer/BrainAnalyzer
/opt/anaconda3/bin/python launcher.py
```

### 使用步骤

1. **选择 DICOM 文件夹** — 选择包含多序列子文件夹的受试者根目录（如 `18zhengjiacheng_00002863_185141/`），软件自动识别所有序列
2. **（可选）自定义输出目录** — 默认在 DICOM 同级创建 `brain_analyzer_output/`
3. **配置分析选项** — 根据需要勾选：
   - fMRI 分析（ALFF/ReHo/图论/动态FC）
   - 高级预处理（运动估计 / Nuisance Regression / Schaefer Atlas）
   - 多模态分析（T1 / DTI / QSM）
   - 报告格式（PDF / Word / 中英双语）
4. **点击 ▶ 开始分析** — 等待进度条完成（通常 30–600 秒）
5. **查看结果** — 在"分析结果"标签页查看摘要，在输出目录查看完整报告

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 选择 DICOM 文件夹 |
| `Ctrl+D` | 切换深色/浅色模式 |
| `Ctrl+Q` | 退出 |

---

## 分析流程详解

```
DICOM 文件夹
    │
    ├── 自动序列识别（BOLD / T1 / DTI / QSM）
    │
    ▼
dcm2niix 转换（UIH Mosaic 自动解码，提取 SliceTiming）
    │
    ├── fMRI BOLD ────────────────────────────────────────────────────┐
    │   ├── 丢弃前 5 TR（steady-state 稳定）                          │
    │   ├── 切片时间校正（STC，线性插值）                              │
    │   ├── 脑掩码（强度 65th% + 形态学）                             │
    │   ├── PSC 标准化 → 线性去趋势                                   │
    │   ├── 运动估计（相位相关法 → FD mm）                            │
    │   ├── Nuisance Regression（6/24 运动参数 + WM/CSF）             │
    │   ├── 带通滤波（0.01–0.1 Hz, Butterworth 4 阶）                 │
    │   └── 空间平滑（FWHM = 6mm）                                    │
    │                                                                  │
    ├── QC ──────────────────────────────────────────────────────────┤
    │   ├── DVARS / FD / tSNR                                         │
    │   ├── Carpet Plot（grayplot）                                   │
    │   └── Scrubbing 建议（FD>0.5 或 DVARS>5%）                     │
    │                                                                  │
    ├── FC 分析（33 MNI-ROI / Schaefer-100/200/400）──────────────── ┤
    │   ├── Pearson r 矩阵 + Fisher-Z                                  │
    │   ├── 8 大脑网络内部统计（DMN/SN/ECN/SMN/VIS/DAN/LMB/SUB）    │
    │   └── PCC 种子连接 + DMN 专项分析                               │
    │                                                                  │
    ├── 局部指标（ALFF / fALFF / ReHo）──────────────────────────── ┤
    │   └── z-score 归一化，NIfTI 图谱保存                            │
    │                                                                  │
    ├── 图论分析（NetworkX）─────────────────────────────────────── ┤
    │   └── CC / GE / LE / σ / Q / Hub 脑区 + 参与系数               │
    │                                                                  │
    ├── 动态 FC（Sliding Window）────────────────────────────────── ┤
    │   └── 44 TP × 2s 窗口，K-means k=2 脑状态聚类                  │
    │                                                                  │
    ├── T1 结构像 ────────────────────────────────────────────────── ┤
    │   └── GMM 3 类分割 → GM/WM/CSF 体积 + 对称性                   │
    │                                                                  │
    ├── DTI 弥散（可选）──────────────────────────────────────────── ┤
    │   └── OLS 张量拟合 → FA/MD/AD/RD + 13 WM 束 ROI               │
    │                                                                  │
    ├── QSM 铁沉积（可选）───────────────────────────────────────── ┤
    │   └── 14 深部灰质 ROI 磁化率统计                                │
    │                                                                  │
    └── 报告生成 ◀────────────────────────────────────────────────────┘
        ├── 10 HTML 交互图表（Plotly）
        ├── 中文 PDF（15 章节，1.8 MB）
        ├── 英文 PDF
        ├── Word (.docx)
        ├── pipeline_config.yaml（配置快照）
        └── reproducibility.json（SHA-256 哈希）
```

---

## 输出文件说明

```
brain_analyzer_output/
├── nifti/
│   ├── bold.nii.gz                   # 原始 4D BOLD（dcm2niix）
│   ├── bold.json                     # BIDS sidecar（TR, SliceTiming...）
│   └── preprocessed_bold.nii.gz      # 预处理后 BOLD
│
├── results/
│   ├── scan_parameters.json          # 扫描参数
│   ├── qc_metrics.json               # QC 评分、tSNR、DVARS、FD
│   ├── scrubbing_result.json         # Scrubbing 建议
│   ├── FC_pearson.npy                # 33×33 功能连接矩阵
│   ├── FC_fisherZ.npy
│   ├── roi_timeseries.npy            # ROI 时间序列
│   ├── network_stats.json            # 8 脑网络统计
│   ├── ALFF_map.npy / fALFF_map.npy / ReHo_map.npy
│   ├── alff_z.nii.gz / falff_z.nii.gz / reho_z.nii.gz
│   ├── graph_metrics.json            # 图论指标
│   ├── dFC_results.json              # 动态 FC
│   ├── motion_params_6dof.txt        # 运动参数（6 列）
│   ├── fd_mm.npy                     # FD（mm）时间序列
│   ├── carpet_plot.png               # Carpet Plot
│   ├── t1_results.json               # T1 分析结果
│   ├── dti_results.json              # DTI 分析结果
│   ├── qsm_results.json              # QSM 分析结果
│   ├── pipeline_config.yaml          # 完整管线配置
│   └── reproducibility.json          # SHA-256 可重复性哈希
│
├── plots/                            # 10 个 Plotly HTML 交互图表
│   ├── 01_FC_matrix.html
│   ├── 02_QC_metrics.html
│   ├── 03_DMN_network.html
│   ├── 04_network_strength.html
│   ├── 05_dynamic_FC.html
│   ├── 06_graph_theory.html
│   ├── 07_ROI_timeseries.html
│   └── 08_ALFF/fALFF/ReHo_brain.html
│
├── report_imgs/                      # PNG 报告图像（报告用）
│
├── multimodal/                       # 多模态 NIfTI 结果
│   ├── t1_tissue_seg.nii.gz          # T1 组织分割
│   ├── dti_FA.nii.gz / dti_MD.nii.gz
│   └── （QSM 数据直接引用原始 NIfTI）
│
└── reports/
    ├── fMRI_Report_<id>_zh.pdf       # 中文 PDF（~1.8 MB）
    ├── fMRI_Report_<id>_en.pdf       # 英文 PDF
    └── fMRI_Report_<id>_zh.docx      # Word 报告
```

---

## 已测试设备与数据

| 项目 | 详情 |
|------|------|
| 扫描仪 | UIH uMR 790（联影医疗），3.0 T |
| 采集机构 | 山东省精神卫生中心 |
| BOLD 序列 | `epi_bold_mww`，64×64×33 slice×240 TR，TR=2s，TE=30ms，FWHM≈3.5mm |
| BOLD 格式 | UIH SaveBySlice Mosaic（384×384 px 存储 6×6=36 tiles） |
| T1 序列 | `t1_gre_fsp_3d_sag_1mm`，1mm 各向同性，192×220×256 |
| DTI 序列 | `epi_hardi64_2b`，64 方向，b=0/990/1985 s/mm²，2mm |
| QSM 序列 | `qsm_traa_QSM`，1mm |
| 运行时间（无 ReHo/DTI）| **~30 秒** |
| 运行时间（含 ReHo）| **~5–10 分钟** |
| 运行时间（含 DTI）| **~10–20 分钟** |

---

## 预处理方法对比

| 步骤 | Brain Analyzer v2.0 | 金标准（fMRIPrep） |
|------|--------------------|--------------------|
| DICOM → NIfTI | dcm2niix ✅ | dcm2niix ✅ |
| 切片时间校正 | 线性插值 ✅ | 3D-SINC ⭐ |
| 头动矫正 | 相位相关（3D 平移）⚠ | MCFLIRT 6-DOF ⭐ |
| 颅骨剥离 | 强度阈值 ⚠ | BET / ANTs ⭐ |
| MNI 配准 | 近似 MNI 坐标映射 ⚠ | ANTs SyN ⭐ |
| 噪声回归 | 6/24 运动参数 + WM/CSF ✅ | FD-based + aCompCor ⭐ |
| ICA-AROMA | 未实现 ❌ | 支持 ⭐ |
| 带通滤波 | Butterworth filtfilt ✅ | 支持 ✅ |
| 空间平滑 | Gaussian FWHM=6mm ✅ | 支持 ✅ |

> ⚠ 表示相较金标准有简化，不影响探索性分析结果的有效性，但建议研究发表前使用 fMRIPrep 完整流程重新处理。

---

## 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| **v2.1** | 2026-07-05 | 高级预处理（运动估计 / Nuisance Regression / Carpet Plot）；Schaefer-2018 Atlas；可重复性哈希；GUI 三段式布局优化 |
| **v2.0** | 2026-07-05 | 完全重写引擎（dcm2niix 精确 Mosaic 解码）；STC；NetworkX 图论；多模态 T1/DTI/QSM；15 章节 PDF |
| **v1.0.7** | 2026-07 | 修复 graph_theory_analysis 空字典 KeyError |
| **v1.0.6** | 2026-07 | 自动识别 BOLD 序列；修复 UIH 无 ImagePositionPatient 标签 |
| **v1.0.0** | 2026-07 | 初始版本 |

---

## 项目结构

```
BrainAnalyzer/
├── launcher.py                        # 一键启动入口
├── README.md                          # 本文档
└── src/
    ├── main.py                        # 程序入口
    ├── core/
    │   ├── analyzer.py                # 主分析引擎（fMRI 全流程）
    │   ├── advanced_preprocessing.py  # 高级预处理模块
    │   ├── multimodal_analyzer.py     # 多模态分析（T1/DTI/QSM）
    │   └── report_generator.py        # PDF/Word 报告生成
    └── gui/
        ├── main_window.py             # 主窗口 GUI
        ├── disclaimer_dialog.py        # 启动免责声明
        └── styles.py                  # 主题样式（浅色/深色）
```

---

## 免责声明

⚠ **本软件仅供科研参考，不构成任何医学诊断依据。**

- 本软件生成的所有报告属于探索性科研分析，不可作为临床诊断、疾病确认或治疗建议的依据
- 单受试者数据不具备统计学推断意义
- 如需临床评估，请咨询有执照的医学专业人员
- 分析结果存在方法学局限性（见报告第十一章）

---

<div align="center">

由 [Karcen Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发 · © 2026 NeuroLab

</div>
