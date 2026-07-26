# Brain Analyzer V3.0 · 脑影像自动分析软件

> 静息态 fMRI 脑网络自动化分析工具 · Resting-state fMRI brain-network analysis toolkit
> 由 [Jiacheng Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发

---

## 🆕 V3.0 更新摘要 · What’s New in V3.0

- **PDF 与 Word 同源生成**：两种格式共用同一套报告内容结构，章节、指标、解释和免责声明保持一致。
- **报告表格重新适配 A4**：中英文单元格自动换行，超宽列按正文宽度缩放，跨页时重复表头。
- **图论阈值统一**：当前流程将全局效率（GE）`0.50–0.80` 作为项目预设探索性区间；`<0.50` 标记为偏低，`>0.80` 标记为偏高。
- **疾病对照降级为非诊断性规则展示**：仅显示“探索性规则命中 X/Y 项”，不再输出“低 / 中度 / 高度疾病相似度”。
- **方法学边界更明确**：GE、FC、Hub 等指标均受 ROI、阈值、密度和预处理流程影响，项目预设区间不能替代同流程健康对照常模。
- **文献与可追溯性修正**：修正 ADHD 文献出处，并明确群体统计差异不能直接转化为个体诊断阈值。

- **Shared PDF/Word source**: both formats now use the same report content model, keeping sections, metrics, interpretations, and disclaimers aligned.
- **A4-safe tables**: Chinese and English cells wrap automatically, oversized columns are scaled to the printable width, and headers repeat across pages.
- **Consistent graph thresholds**: for this pipeline, GE `0.50–0.80` is treated as a preset exploratory project interval; values below `0.50` are flagged low and values above `0.80` high.
- **Non-diagnostic literature comparison**: the report shows “X/Y exploratory rules matched” instead of low/moderate/high disease-similarity labels.
- **Clearer methodological limits**: GE, FC, and hub results depend on the ROI set, threshold, density, and preprocessing pipeline; project presets are not a substitute for matched healthy-control norms.

---

## ⚠️ 使用限制 · Usage Restriction

> **🚫 严禁非医学相关人员使用。本软件仅供科研参考，不作为临床诊断依据。**
>
> **🚫 For medical / research professionals only. This software is a research reference tool and must NOT be used for clinical diagnosis.**

启动时会弹出临床警告对话框，必须逐条勾选三项声明后方可进入。生成的所有结果（FC 矩阵、ALFF/fALFF、ReHo、图论指标、疾病文献对照等）均为科研探索性输出，**不构成任何医学诊断、治疗建议或健康结论**。

A clinical-warning dialog is shown on startup; you must acknowledge all three declarations before use. Every output (FC matrices, ALFF/fALFF, ReHo, graph metrics, literature comparisons) is exploratory research material and **does not constitute medical diagnosis, treatment advice, or any health conclusion.**

---

## ❓ 常见问题（先读这里）· FAQ (read this first)

这三个问题最常被问到，直接放在最前面。
These are the three most common questions, answered up front.

### 1. 这个软件运行需要联网吗？ · Does it need an internet connection?

**中文：** 不需要。核心分析**完全离线**运行——DICOM 导入、预处理、功能连接、ALFF/fALFF、ReHo、图论、动态 FC、PDF 报告，全部在本地完成，不向任何服务器发送数据。
唯一的例外：在「高级预处理」中若手动勾选使用 **Schaefer-2018 脑图谱**，nilearn 会在**首次使用时尝试联网下载一次**该图谱并缓存到本地（之后离线可用）；下载失败会**自动回退到内置的 33 个 MNI 球形 ROI**（默认方案，本身就离线）。此外 fMRIPrep 由你在本地 Docker 中运行，软件只读取其结果，不联网。

**English:** No. The core analysis runs **fully offline** — DICOM import, preprocessing, functional connectivity, ALFF/fALFF, ReHo, graph theory, dynamic FC, and PDF reporting all happen locally, and no data is ever sent to any server.
The only exception: if you manually enable the **Schaefer-2018 atlas** under Advanced Preprocessing, nilearn will **try to download it once on first use** and cache it locally (offline thereafter). If the download fails it **automatically falls back to the built-in 33 MNI spherical ROIs** (the default, which is offline anyway). fMRIPrep itself runs in your own local Docker; the software only reads its outputs and never goes online.

### 2. 它会自动搜索最新文献然后给出判断吗？ · Does it automatically search the latest literature and make a judgment?

**中文：** 检索文献「会，但仅可选且默认关闭」；下判断「绝不会」。
- **默认（关闭）**：完全离线，报告的「文献对照」使用内置静态文献和**项目预设探索性区间**。这些区间用于保持当前分析流程内部解释一致，**不是可跨图谱、跨阈值或跨软件直接套用的健康成人临床常模**。
- **可选（勾选「联网更新最新文献」）**：软件通过 **NCBI PubMed 官方免费接口（E-utilities，无需密钥）**，按「疾病 + 脑网络」关键词检索**最近数年的最新论文**，把最新参考文献追加进报告第十章的疾病对照表。结果本地缓存约 30 天；离线或超时会**自动回退**到内置静态引用，不影响报告生成。
- **隐私**：联网时**只发送疾病名与通用神经科学检索词**（如 `major depressive disorder resting-state functional connectivity`），**绝不发送任何受试者数据、影像或分析结果**。
- **它始终不会替你下诊断结论**——文献只是供人工参考的对照材料。第十章仅列出项目预设探索性规则的逐项命中情况，不生成疾病相似度等级，并明确标注「仅为科研文献对照，不构成任何医学诊断」。

**English:** Searching literature: "yes, but optional and off by default." Making a judgment: "never."
- **Default (off):** Fully offline. The report's literature comparison uses built-in static references and **preset exploratory project intervals**. These intervals keep interpretation internally consistent for the current pipeline; they are **not universal healthy-adult clinical norms that can be transferred across atlases, thresholds, or software**.
- **Optional (tick "Update literature online"):** The software queries the **official free NCBI PubMed API (E-utilities, no key required)** with "disease + brain-network" search terms to retrieve the **most recent papers of the last few years**, and appends those citations to the disease-comparison table in report Section 10. Results are cached locally (~30 days); if offline or timed out it **automatically falls back** to the built-in static citations without breaking report generation.
- **Privacy:** When online, it **only sends disease names and generic neuroscience search terms** (e.g. `major depressive disorder resting-state functional connectivity`) and **never sends any subject data, imaging, or analysis results.**
- **It never makes a diagnostic conclusion for you** — Section 10 only shows which preset exploratory rules were matched, does not assign a disease-similarity level, and is always labelled "research reference only, not a medical diagnosis."

### 3. 那它到底是什么？它是怎么工作的？ · So what is it, and how does it work?

**中文：** 它是一个**本地运行的静息态 fMRI 脑网络分析工具**。工作流程：
输入（DICOM 序列 **或** 已用 fMRIPrep 处理好的数据）→ 预处理（内置粗略流程，或直接读取 fMRIPrep 金标准结果）→ 计算脑功能指标（功能连接 FC、ALFF/fALFF、ReHo、图论网络指标、动态 FC）→ 输出 PDF 报告、图表、矩阵文件。
支持**单人分析**与**队列/批量分析**两种模式，队列模式会串行处理多个受试者并汇总组级统计导出 CSV。

**English:** It is a **locally-run resting-state fMRI brain-network analysis tool**. The workflow:
Input (a DICOM series **or** data already processed by fMRIPrep) → Preprocessing (built-in rough pipeline, or read fMRIPrep gold-standard derivatives directly) → Compute brain metrics (functional connectivity, ALFF/fALFF, ReHo, graph-theory network metrics, dynamic FC) → Output a PDF report, figures, and matrix files.
It supports both **single-subject** and **cohort/batch** modes; cohort mode processes subjects serially and aggregates group-level statistics into a CSV.

---

## ✨ 功能 · Features

| 中文 | English |
|------|---------|
| 两种模式：单人分析 + 队列/批量分析 | Single-subject and cohort/batch modes |
| 两种输入：原始 DICOM 或 fMRIPrep 结果 | Two inputs: raw DICOM or fMRIPrep derivatives |
| 主流 MRI 厂商 DICOM 自动识别 | Auto-detection of major MRI-vendor DICOM |
| 功能连接（FC）矩阵与网络分析 | Functional connectivity matrices & network analysis |
| ALFF / fALFF / ReHo 局部指标 | ALFF / fALFF / ReHo local metrics |
| 图论网络指标（小世界性、全局效率等） | Graph-theory metrics (small-worldness, global efficiency, …) |
| 动态功能连接（dynamic FC） | Dynamic functional connectivity |
| 队列组级统计 + CSV 导出 | Cohort group-level statistics + CSV export |
| 自动生成 PDF / Word 报告（同一内容源、章节一致） | PDF / Word reports from one shared content source |
| A4 表格自动换行、列宽适配和跨页表头 | A4-safe wrapping, column scaling, and repeated table headers |
| 疾病文献对照仅显示探索性规则命中数 | Disease literature comparison reports exploratory rule counts only |
| 可选：联网更新最新文献（PubMed） | Optional: online literature update (PubMed) |
| 纯黑白高对比界面，支持深/浅色系统 | Clean high-contrast B&W UI, dark/light OS safe |

---

## 🔬 两种分析模式 · Two Analysis Modes

- **🔬 单人分析 / Single-subject** — 分析单个受试者，生成完整报告。
- **👥 队列分析 / Cohort** — 添加多个受试者（或用「批量添加」选父目录自动扫描），串行处理并汇总组级统计，导出 `cohort_summary.csv`、`group_stats.json`、`group_mean_FC.npy` 到 `<输出目录>/_group/`。先支持小队列，后期可扩展。

---

## 🧠 两种预处理路径 · Two Preprocessing Paths

1. **fMRIPrep 金标准（推荐用于严肃科研） / fMRIPrep gold standard (recommended)**
   你在本地用 Docker 自行运行 fMRIPrep，然后把结果目录导入本软件。软件读取 `desc-preproc_bold.nii.gz`、`desc-confounds_timeseries.tsv`、脑掩膜等，支持 6P / 24P / 36P / aCompCor 混杂回归策略。**软件不替你跑 fMRIPrep**——详见 [docs/FMRIPREP_GUIDE.md](docs/FMRIPREP_GUIDE.md)（Docker 安装 → BIDS 转换 → 运行 fMRIPrep → 导入）。

2. **内置粗略预处理（无 fMRIPrep 数据时） / Built-in rough preprocessing (fallback)**
   若没有 fMRIPrep 结果，软件用内置流程做粗略预处理（时间层校正、运动估计、去噪回归、带通滤波、平滑）。适合快速探索，**不建议**作为严肃科研或任何临床相关用途的依据。

---

## 📄 报告说明 · Reports

生成的 **PDF 与 Word 报告由同一内容模型生成**，中文报告包含：

1. 扫描参数与数据概览
2. 数据预处理流程
3. 数据质量控制（QC）
4. ROI 定义与静息态脑网络分析
5. 默认模式网络（DMN）专项分析
6. 全脑功能连接分析
7. 局部脑活动分析（ALFF / fALFF / ReHo）
8. 脑功能网络图论分析
9. 动态功能连接分析
10. 神经精神疾病脑网络文献对照分析
11. 神经科学讨论
12. 方法学说明与可重复性
13. 附录：全部 ROI 图论指标

存在 T1、DTI、QSM 等结果时，会追加多模态综合分析内容。报告支持中文和英文输出。

**第十章「神经精神疾病脑网络文献对照」** 把本受试者的脑网络指标与已发表群体研究做**探索性对照**，覆盖 MDD、BD、SCZ、ADHD、ASD、GAD、OCD、PTSD、AD、PD 十类。表格逐项显示项目预设规则是否命中，并汇总为“X/Y 项规则命中（非诊断）”；**不再生成低、中度或高度疾病相似度等级**。表中引用可通过「联网更新最新文献」补充 PubMed 论文。

The generated **PDF and Word reports use the same content model**, covering scan/data overview, preprocessing, QC, ROI/network analysis, DMN, whole-brain FC, ALFF/fALFF/ReHo, graph theory, dynamic FC, neuropsychiatric literature comparison, discussion, reproducibility, and a complete ROI appendix. Multimodal content is appended when T1, DTI, or QSM results are available. Chinese and English output are supported.

**Section 10, "Neuropsychiatric Disease Brain-Network Literature Comparison,"** performs an **exploratory comparison** across ten conditions (MDD, BD, SCZ, ADHD, ASD, GAD, OCD, PTSD, AD, PD). It reports only how many preset exploratory rules were matched and does not assign low/moderate/high disease similarity. **It is explicitly non-diagnostic.**

---

## 🔎 文献自动更新（可选） · Literature Auto-Update (optional)

- 在「报告生成」勾选 **「联网更新最新文献」**（默认关闭）即可启用。
- 数据源：**NCBI PubMed E-utilities**（官方免费接口，无需 API 密钥），检索最近数年、按日期排序的最新论文。
- 缓存：结果写入本地 `~/.brain_analyzer_litcache.json`（默认 30 天有效），避免重复请求。
- 兜底：无网络 / 超时 / 关闭时，自动使用内置静态引用，报告照常生成。
- 隐私：**只发送疾病名 + 通用神经科学关键词，绝不发送任何受试者数据。**

- Enable it by ticking **"Update literature online"** under "Report generation" (off by default).
- Source: **NCBI PubMed E-utilities** (official free API, no key required), fetching the most recent date-sorted papers of the last few years.
- Cache: results are written to `~/.brain_analyzer_litcache.json` locally (valid ~30 days) to avoid repeated requests.
- Fallback: when offline / timed out / disabled, built-in static citations are used and the report is generated as usual.
- Privacy: **only disease names + generic neuroscience keywords are sent; no subject data is ever transmitted.**

---

## 📦 安装 · Installation

```bash
# 需要 Python 3.9+ 与以下依赖 / Requires Python 3.9+ and:
pip install PyQt5 numpy scipy scikit-learn nibabel pydicom \
            reportlab python-docx matplotlib networkx nilearn
```

- fMRIPrep 金标准路径额外需要本地 **Docker**（用于运行 fMRIPrep，非本软件依赖）。
- The fMRIPrep path additionally needs local **Docker** (to run fMRIPrep itself, not a dependency of this app).

---

## 🚀 运行 · Run

```bash
python launcher.py     # 自动选用含科学栈的解释器 / auto-selects the scientific Python
# 或 / or
python src/main.py
```

启动后先通过临床警告对话框（勾选三项声明），再选择模式与输入。
On launch, pass the clinical-warning dialog (check all three declarations), then choose a mode and input.

---

## 📁 项目结构 · Project Structure

```
fMRI-GUI-BrainAnalyzer/
├── launcher.py                       # 启动脚本 / launcher
├── README.md
├── docs/
│   └── FMRIPREP_GUIDE.md             # fMRIPrep 完整指引 / full fMRIPrep guide
└── src/
    ├── main.py                       # 入口 / entry point
    ├── version.py                    # V3.0 单一版本信息源 / version source
    ├── gui/
    │   ├── main_window.py            # 主窗口（单人 + 队列）/ main window
    │   ├── clinical_warning_dialog.py# 临床警告框 / clinical warning
    │   └── styles.py                 # 黑白主题 / B&W theme
    └── core/
        ├── analyzer.py               # 单人分析流程 / single-subject pipeline
        ├── cohort_analyzer.py        # 队列分析 / cohort pipeline
        ├── fmriprep_loader.py        # fMRIPrep 结果读取 / fMRIPrep loader
        ├── advanced_preprocessing.py # 高级预处理 / advanced preprocessing
        ├── multimodal_analyzer.py    # 多模态分析 / multimodal analysis
        ├── literature_updater.py     # 文献自动更新（PubMed）/ literature auto-update
        └── report_generator.py       # 报告生成 / report generator
```

---

## 🧾 版本记录 · Changelog

### V3.0 — 2026-07-26

- 统一 PDF 与 Word 报告内容源和章节结构。
- 修复中文表格文字越界、超宽列和跨页表头问题。
- 统一第八章与第十章的 GE 解释口径，修复 `GE=0.603<0.30` 等错误表达。
- 将疾病“相似度等级”替换为非诊断性的探索性规则命中数。
- 补充图论阈值依赖性说明，修正文献出处。
- 完成报告生成、版本标识与阈值逻辑回归验证。

---

## ⚖️ 免责声明 · Disclaimer

本软件按「现状」提供，仅用于科学研究与教育目的。作者不对使用本软件产生的任何直接或间接后果负责。**任何涉及健康、诊断、治疗的决定，必须由具备资质的医学专业人员依据规范的临床流程做出，不得依赖本软件的输出。**

This software is provided "as is" for scientific research and educational purposes only. The author accepts no liability for any consequence arising from its use. **Any decision concerning health, diagnosis, or treatment must be made by a qualified medical professional following proper clinical procedures, and must never rely on this software's output.**

---

由 [Jiacheng Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发 · © 2026 NeuroLab

Developed by [Jiacheng Zheng](https://karcen.github.io/zhengjiacheng.github.io/) with Claude Code · © 2026 NeuroLab
