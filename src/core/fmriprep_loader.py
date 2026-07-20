#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fMRIPrep derivatives 加载器
------------------------------------------------------------------
临床/科研金标准：直接读取 fMRIPrep 预处理输出（BIDS derivatives），
使用其 desc-preproc_bold + confounds_timeseries，配合 nilearn 做
标准 confound 回归（无需本机安装 FSL/ANTs）。

若目录中找不到 fMRIPrep 输出，detect() 返回 None，主管线自动回退到
内置的粗略预处理。
"""
import os
import re
import glob
import json

import numpy as np


class FMRIPrepLoader:
    """检测并加载单个受试者的 fMRIPrep derivatives。"""

    # 标准 confound 策略（列名前缀）
    CONFOUND_STRATEGIES = {
        "6P":   ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"],
        "24P":  None,   # 6 运动参数 + 导数 + 平方（下方展开）
        "9P":   ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
                 "white_matter", "csf", "global_signal"],
        "36P":  None,   # 9P + 导数 + 平方（下方展开）
        "aCompCor": None,   # 运动 6 + a_comp_cor_00..05
    }

    def __init__(self, derivatives_dir: str):
        self.root = derivatives_dir
        self.subjects = []      # ['sub-01', ...]

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def looks_like_fmriprep(path: str) -> bool:
        """快速判断一个目录是否是 fMRIPrep derivatives。"""
        if not path or not os.path.isdir(path):
            return False
        # 特征1: 存在 dataset_description.json 且 GeneratedBy 含 fMRIPrep
        dd = os.path.join(path, "dataset_description.json")
        if os.path.isfile(dd):
            try:
                with open(dd, encoding="utf-8") as f:
                    meta = json.load(f)
                gen = json.dumps(meta.get("GeneratedBy", meta), ensure_ascii=False)
                if "fmriprep" in gen.lower():
                    return True
            except Exception:
                pass
        # 特征2: 存在 sub-*/func/*desc-preproc_bold.nii.gz
        hits = glob.glob(os.path.join(
            path, "sub-*", "**", "*desc-preproc_bold.nii.gz"), recursive=True)
        return len(hits) > 0

    # ─────────────────────────────────────────────────────────────────────────
    def detect_subjects(self) -> list:
        """列出 derivatives 中的所有受试者 ID。"""
        subs = set()
        for p in glob.glob(os.path.join(self.root, "sub-*")):
            name = os.path.basename(p)
            if os.path.isdir(p) and re.match(r"sub-[A-Za-z0-9]+$", name):
                subs.add(name)
        self.subjects = sorted(subs)
        return self.subjects

    # ─────────────────────────────────────────────────────────────────────────
    def find_bold(self, subject: str, space: str = "MNI152NLin2009cAsym") -> dict:
        """
        找到某受试者的首个 preproc BOLD + 对应 confounds/mask。
        优先标准空间 (space-MNI...)，其次原生空间 (无 space 标签)。
        Returns dict(bold, confounds, mask, json) 或 None。
        """
        func_glob = os.path.join(self.root, subject, "**", "func")
        func_dirs = glob.glob(func_glob, recursive=True) or \
            [os.path.join(self.root, subject, "func")]

        candidates = []
        for fd in func_dirs:
            candidates += glob.glob(os.path.join(fd, "*desc-preproc_bold.nii.gz"))

        if not candidates:
            return None

        # 优先带指定 space 的
        def rank(fp):
            if f"space-{space}" in fp:
                return 0
            if "space-" not in os.path.basename(fp):
                return 1        # 原生空间
            return 2
        candidates.sort(key=rank)
        bold = candidates[0]

        # 关联文件：把 desc-preproc_bold.nii.gz 换成对应后缀
        base = bold.replace("_desc-preproc_bold.nii.gz", "")
        # confounds 不带 space 标签
        conf_base = re.sub(r"_space-[A-Za-z0-9]+", "", base)
        confounds = conf_base + "_desc-confounds_timeseries.tsv"
        mask = base + "_desc-brain_mask.nii.gz"
        sidecar = bold.replace(".nii.gz", ".json")

        return {
            "bold":      bold,
            "confounds": confounds if os.path.isfile(confounds) else None,
            "mask":      mask if os.path.isfile(mask) else None,
            "json":      sidecar if os.path.isfile(sidecar) else None,
            "space":     space if f"space-{space}" in bold else "native",
        }

    # ─────────────────────────────────────────────────────────────────────────
    def _read_confounds_tsv(self, tsv_path: str) -> tuple:
        """读取 confounds TSV → (header list, data ndarray[nt, ncol])。"""
        with open(tsv_path, encoding="utf-8") as f:
            header = f.readline().rstrip("\n").split("\t")
        data = np.genfromtxt(tsv_path, delimiter="\t", skip_header=1,
                             filling_values=0.0)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return header, data

    def build_confound_matrix(self, tsv_path: str, strategy: str = "24P") -> np.ndarray:
        """
        根据策略从 fMRIPrep confounds TSV 构建回归矩阵。
        支持 6P / 9P / 24P / 36P / aCompCor。
        """
        header, data = self._read_confounds_tsv(tsv_path)
        col = {name: i for i, name in enumerate(header)}

        def get(name):
            if name in col:
                v = data[:, col[name]].astype(float)
                return np.nan_to_num(v, nan=0.0)
            return None

        motion6 = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
        cols = []

        if strategy in ("6P", "24P"):
            base = motion6
        elif strategy in ("9P", "36P"):
            base = motion6 + ["white_matter", "csf", "global_signal"]
        elif strategy == "aCompCor":
            base = motion6
        else:
            base = motion6

        for nm in base:
            v = get(nm)
            if v is not None:
                cols.append(v)

        # 展开：导数 + 平方（24P / 36P）
        if strategy in ("24P", "36P"):
            expanded = []
            for v in list(cols):
                deriv = np.concatenate([[0.0], np.diff(v)])
                expanded.append(deriv)
            sqs = [v ** 2 for v in cols]
            dsqs = [d ** 2 for d in expanded]
            cols = cols + expanded + sqs + dsqs

        # aCompCor 分量
        if strategy == "aCompCor":
            for i in range(6):
                v = get(f"a_comp_cor_{i:02d}")
                if v is not None:
                    cols.append(v)

        if not cols:
            return np.zeros((data.shape[0], 0))
        return np.column_stack(cols)

    # ─────────────────────────────────────────────────────────────────────────
    def get_fd(self, tsv_path: str) -> np.ndarray:
        """从 confounds 提取 framewise_displacement (mm)。"""
        header, data = self._read_confounds_tsv(tsv_path)
        if "framewise_displacement" in header:
            v = data[:, header.index("framewise_displacement")].astype(float)
            return np.nan_to_num(v, nan=0.0)
        return np.zeros(data.shape[0])

    # ─────────────────────────────────────────────────────────────────────────
    def clean_bold(self, files: dict, output_dir: str,
                   strategy: str = "24P", tr: float = 2.0, TR: float = None,
                   bandpass=(0.01, 0.1), fwhm: float = 6.0,
                   progress_cb=None) -> str:
        """
        对 fMRIPrep preproc BOLD 应用金标准 confound 回归。
        使用 nilearn.image.clean_img（去趋势 + confound 回归 + 带通 + 标准化）。
        返回清洗后 NIfTI 路径，格式与内置管线 preprocess() 输出兼容。

        额外产出下游 QC / carpet plot 所需的中间文件（与内置管线一致）：
          brain_mask.npy, ts_raw_brain.npy, data_preprocessed.npy
        """
        import nibabel as nib
        from nilearn.image import clean_img, smooth_img

        if TR is not None:
            tr = TR

        def cb(p, m):
            if progress_cb:
                progress_cb(p, m)

        os.makedirs(output_dir, exist_ok=True)
        bold = files["bold"]
        cb(30, f"加载 fMRIPrep preproc BOLD ({files.get('space','?')} 空间)...")

        img = nib.load(bold)

        # ── 脑掩码：优先用 fMRIPrep 输出的 brain mask，否则强度阈值 ──────────
        cb(31, "生成脑掩码...")
        raw4d = img.get_fdata(dtype=np.float32)
        if files.get("mask"):
            mask = nib.load(files["mask"]).get_fdata() > 0.5
        else:
            mean_vol = raw4d.mean(axis=3)
            mask = mean_vol > np.percentile(mean_vol[mean_vol > 0], 40)
        mask = mask.astype(bool)
        np.save(os.path.join(output_dir, "brain_mask.npy"), mask)

        # 原始脑内时间序列（tSNR / DVARS 用，清洗前）
        ts_raw_brain = raw4d[mask]   # (n_vox, nt)
        np.save(os.path.join(output_dir, "ts_raw_brain.npy"), ts_raw_brain)

        # confound 矩阵
        confounds = None
        if files.get("confounds"):
            cb(33, f"构建 confound 回归矩阵 (策略={strategy})...")
            confounds = self.build_confound_matrix(files["confounds"], strategy)
            # 首帧导数为0已处理；替换潜在 nan
            confounds = np.nan_to_num(confounds, nan=0.0)

        cb(36, "confound 回归 + 带通滤波 + 标准化 (nilearn.clean_img)...")
        low, high = bandpass
        cleaned = clean_img(
            img,
            detrend=True,
            standardize="zscore_sample",
            confounds=confounds,
            low_pass=high,
            high_pass=low,
            t_r=tr,
            ensure_finite=True,
        )

        if fwhm and fwhm > 0:
            cb(38, f"空间平滑 FWHM={fwhm}mm...")
            cleaned = smooth_img(cleaned, fwhm)

        out = os.path.join(output_dir, "preprocessed_fmriprep.nii.gz")
        nib.save(cleaned, out)

        # 平滑后 4D（carpet plot / WM-CSF 提取用），与内置管线键名一致
        np.save(os.path.join(output_dir, "data_preprocessed.npy"),
                cleaned.get_fdata(dtype=np.float32))

        cb(40, "fMRIPrep 数据清洗完成")
        return out
