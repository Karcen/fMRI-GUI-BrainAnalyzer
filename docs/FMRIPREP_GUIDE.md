# fMRIPrep 金标准预处理指南

> 本指南面向准备将 Brain Analyzer 用于**临床科研**的用户。
> Brain Analyzer 本身**不运行** fMRIPrep —— 它负责读取 fMRIPrep 已处理好的
> derivatives 数据并完成下游脑网络分析。fMRIPrep 需你在本机通过 Docker 运行一次。

---

## 为什么用 fMRIPrep

Brain Analyzer 内置了一套纯 Python 预处理管线（相位相关运动估计、带通滤波、
平滑、nuisance regression），足以支撑探索性分析。但它**不是临床金标准**：

| 步骤 | 内置管线 | fMRIPrep 金标准 |
|------|---------|----------------|
| 头动矫正 | 相位相关（3-DOF 近似） | MCFLIRT / ANTs（6-DOF，亚体素）|
| 颅骨剥离 | 强度阈值 | ANTs + OASIS 模板 |
| 空间配准 | 无（原生空间近似）| ANTs SyN 非线性配准到 MNI152 |
| 组织分割 | GMM 近似 | FSL FAST |
| 噪声回归 | 6/24 运动 + WM/CSF | aCompCor / ICA-AROMA / 全套 confounds |
| 失真校正 | 无 | SDC（fieldmap / SynSDC）|

**若数据要用于临床研究或论文发表，强烈建议使用 fMRIPrep 预处理。**

---

## 一、安装 Docker Desktop

fMRIPrep 以 Docker 容器分发，是运行它最简单可靠的方式。

### macOS

1. 访问 <https://www.docker.com/products/docker-desktop/> 下载 **Docker Desktop for Mac**
   - Apple Silicon（M1/M2/M3/M4）选 **Apple Chip** 版本
   - Intel Mac 选 **Intel Chip** 版本
2. 双击 `.dmg` 安装，把 Docker 拖入 Applications
3. 启动 Docker Desktop，等待顶部菜单栏 🐳 图标变为稳定（表示 daemon 已运行）
4. 在设置 **Settings → Resources** 中，建议分配：
   - **Memory ≥ 16 GB**（fMRIPrep 最低 8 GB，推荐 16 GB）
   - **Disk ≥ 50 GB**（镜像约 15 GB + 工作文件）

### 验证 Docker 可用

```bash
docker --version
docker info        # 若报 "Cannot connect to the Docker daemon"，说明 Docker Desktop 未启动
docker run hello-world   # 成功打印欢迎信息即 OK
```

---

## 二、准备 BIDS 格式数据

fMRIPrep 要求输入符合 [BIDS](https://bids.neuroimaging.io/) 规范。
从 DICOM 转 BIDS 推荐用 **dcm2bids**：

```bash
# 安装 dcm2bids（需 dcm2niix）
/opt/anaconda3/bin/pip install dcm2bids
brew install dcm2niix

# 1) 生成配置脚手架
dcm2bids_scaffold -o bids_dataset

# 2) 用一次样本生成 sidecar 帮助你写映射规则
dcm2bids_helper -d /path/to/dicom/subject01 -o tmp_help

# 3) 编辑 bids_dataset/code/dcm2bids_config.json 定义映射
#    （把 BOLD 序列映射到 func/bold，T1 映射到 anat/T1w）

# 4) 转换每个受试者
dcm2bids -d /path/to/dicom/subject01 -p 01 \
    -c bids_dataset/code/dcm2bids_config.json -o bids_dataset
```

最终目录结构应类似：

```
bids_dataset/
├── dataset_description.json
├── participants.tsv
├── sub-01/
│   ├── anat/sub-01_T1w.nii.gz
│   └── func/sub-01_task-rest_bold.nii.gz
├── sub-02/
│   └── ...
```

用 [BIDS Validator](https://bids-standard.github.io/bids-validator/) 在线校验目录合法性。

---

## 三、运行 fMRIPrep

### 获取 FreeSurfer License（免费）

fMRIPrep 依赖 FreeSurfer，需要一个免费 license 文件：
<https://surfer.nmr.mgh.harvard.edu/registration.html> —— 注册后邮件收到 `license.txt`。

### 单受试者

```bash
docker run --rm -it \
  -v /absolute/path/bids_dataset:/data:ro \
  -v /absolute/path/derivatives:/out \
  -v /absolute/path/license.txt:/opt/freesurfer/license.txt \
  nipreps/fmriprep:23.2.0 \
  /data /out participant \
  --participant-label 01 \
  --output-spaces MNI152NLin2009cAsym:res-2 \
  --fs-license-file /opt/freesurfer/license.txt \
  --nthreads 4 --mem-mb 12000 \
  --skip-bids-validation
```

### 整个队列（所有受试者）

去掉 `--participant-label` 即处理全部：

```bash
docker run --rm -it \
  -v /absolute/path/bids_dataset:/data:ro \
  -v /absolute/path/derivatives:/out \
  -v /absolute/path/license.txt:/opt/freesurfer/license.txt \
  nipreps/fmriprep:23.2.0 \
  /data /out participant \
  --output-spaces MNI152NLin2009cAsym:res-2 \
  --fs-license-file /opt/freesurfer/license.txt \
  --nthreads 8 --mem-mb 16000 \
  --skip-bids-validation
```

**关键参数说明：**

| 参数 | 作用 |
|------|------|
| `--output-spaces MNI152NLin2009cAsym:res-2` | 输出 2mm MNI 标准空间（Brain Analyzer 默认读取此空间）|
| `--fs-license-file` | FreeSurfer license 路径 |
| `--nthreads` / `--mem-mb` | CPU 线程 / 内存（按 Docker 分配调整）|
| `--use-aroma` | 额外运行 ICA-AROMA（可选，更干净但更慢）|
| `--skip-bids-validation` | 已用 validator 校验后可跳过 |

> ⏱ 单受试者约需 **6–24 小时**（取决于 CPU / 是否跑 FreeSurfer 重建）。
> 加 `--fs-no-reconall` 可跳过表面重建，大幅提速（本软件不需要表面数据）。

### 提速：跳过 FreeSurfer 表面重建

```bash
  ... nipreps/fmriprep:23.2.0 /data /out participant \
  --fs-no-reconall \
  --output-spaces MNI152NLin2009cAsym:res-2 \
  ...
```

---

## 四、在 Brain Analyzer 中加载 fMRIPrep 结果

fMRIPrep 完成后，`derivatives/` 目录形如：

```
derivatives/
├── dataset_description.json      ← GeneratedBy 含 "fMRIPrep"
├── sub-01/
│   └── func/
│       ├── sub-01_..._space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz
│       ├── sub-01_..._space-MNI152NLin2009cAsym_desc-brain_mask.nii.gz
│       └── sub-01_..._desc-confounds_timeseries.tsv
├── sub-02/...
```

### 单人分析

1. 打开 Brain Analyzer → **单人分析** Tab
2. 勾选 **「使用 fMRIPrep 预处理数据（金标准）」**
3. 点 **「选择 fMRIPrep derivatives 目录」**，选中上面的 `derivatives/` 目录
4. 选择 confound 策略（默认 24P；追求更干净可选 36P 或 24P+aCompCor）
5. 点 **开始分析**

软件会自动：
- 读取 `desc-preproc_bold`（MNI 空间）
- 用 `confounds_timeseries.tsv` 做标准 confound 回归（nilearn `clean_img`）
- 带通滤波 + 平滑 → 下游 FC / 图论 / 动态 FC 分析

### 队列分析

1. 打开 **队列分析** Tab
2. 输入类型选 **「fMRIPrep 目录（金标准）」**
3. **批量添加（父目录）** 选中包含多个 `derivatives` 的父目录，或逐个 **添加受试者**
4. 选择队列输出目录 → **开始队列分析**

软件串行处理每个受试者，完成后在 `_group/` 目录生成：
- `cohort_summary.csv`（每人一行：QC、tSNR、FD、DMN FC、σ 等）
- `group_stats.json`（组级均值 / 标准差 / 范围）
- `group_mean_FC.npy`（组平均 FC 矩阵，若各人 ROI 维度一致）

---

## 五、confound 策略选择建议

| 策略 | 回归项 | 适用场景 |
|------|--------|---------|
| **24P** | 6 运动 + 导数 + 平方 | 默认，兼顾去噪与自由度 |
| **24P+aCompCor** | 24P + 6 主成分（WM/CSF）| 生理噪声重时更干净 |
| **36P** | 24P + WM/CSF/GS + 导数平方 | 最激进去噪；注意 GSR 争议 |

> ⚠ 全局信号回归（GSR）会引入负相关伪迹，学界有争议。若审稿人反对 GSR，用 24P 或 aCompCor。

---

## 常见问题

**Q：没有 Docker 能用吗？**
可以。不勾选 fMRIPrep 选项时，软件使用内置管线（粗略预处理）直接分析 DICOM。
仅探索性用途够用，但临床研究建议用 fMRIPrep。

**Q：fMRIPrep 报 "Cannot connect to the Docker daemon"？**
Docker Desktop 没启动。打开它，等 🐳 图标稳定后重试。

**Q：内存不足 / 进程被杀？**
调高 Docker Desktop 的 Memory 分配（Settings → Resources），或降低 `--nthreads`。

**Q：软件说"目录不像 fMRIPrep derivatives"？**
确认选的是 fMRIPrep 输出的 `derivatives` 根目录（内含 `sub-*/func/*desc-preproc_bold.nii.gz`），
不是 BIDS 原始数据目录。

---

由 [Karcen Zheng](https://karcen.github.io/zhengjiacheng.github.io/) 使用 Claude Code 辅助开发 · © 2026 NeuroLab
