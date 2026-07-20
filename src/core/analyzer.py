#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心分析引擎 v2.0 — Brain Analyzer
基于 dcm2niix + 完全离线 MNI-coord ROI 管线
算法与验证过的 fmri_analysis/ 脚本完全一致
"""

import os, sys, json, shutil, subprocess, warnings, glob
import numpy as np
import nibabel as nib
import pydicom
from scipy import signal, ndimage
from scipy.ndimage import gaussian_filter
from scipy.stats import rankdata

warnings.filterwarnings('ignore')

# ──────────────────────────────────────────────────────────────────────────────
#  33个 MNI 坐标 ROI（完全离线，无需下载 atlas）
# ──────────────────────────────────────────────────────────────────────────────
ROI_DEFS = {
    "mPFC":        (0,   52,  -6),   # DMN
    "PCC":         (0,  -52,  26),
    "Precuneus":   (0,  -58,  40),
    "L_Angular":   (-46,-66,  36),
    "R_Angular":   (46, -66,  36),
    "L_mTL_HPC":   (-24,-20, -20),
    "R_mTL_HPC":   (24, -20, -20),
    "ACC_dACC":    (0,   32,  28),   # SN
    "L_AI":        (-34, 22,   0),
    "R_AI":        (34,  22,   0),
    "L_dlPFC":     (-42, 36,  20),   # ECN
    "R_dlPFC":     (42,  36,  20),
    "L_IPL":       (-50,-52,  46),
    "R_IPL":       (50, -52,  46),
    "L_M1":        (-38,-24,  54),   # SMN
    "R_M1":        (38, -24,  54),
    "SMA":         (0,   -8,  54),
    "V1_L":        (-12,-90,   4),   # VIS
    "V1_R":        (12, -90,   4),
    "LOC_L":       (-46,-70,   0),
    "L_FEF":       (-28, -8,  54),   # DAN
    "R_FEF":       (28,  -8,  54),
    "L_IPS":       (-26,-60,  48),
    "R_IPS":       (26, -60,  48),
    "L_Amy":       (-20, -6, -18),   # LMB
    "R_Amy":       (20,  -6, -18),
    "L_Thal":      (-12,-20,   8),
    "R_Thal":      (12, -20,   8),
    "L_Caudate":   (-14, 16,   8),   # SUB
    "R_Caudate":   (14,  16,   8),
    "Brainstem":   (0,  -28, -30),
    "L_Cerebellum":(-26,-58, -30),
    "R_Cerebellum":(26, -58, -30),
}

NETWORKS = {
    "DMN":  ["mPFC","PCC","Precuneus","L_Angular","R_Angular","L_mTL_HPC","R_mTL_HPC"],
    "SN":   ["ACC_dACC","L_AI","R_AI"],
    "ECN":  ["L_dlPFC","R_dlPFC","L_IPL","R_IPL"],
    "SMN":  ["L_M1","R_M1","SMA"],
    "VIS":  ["V1_L","V1_R","LOC_L"],
    "DAN":  ["L_FEF","R_FEF","L_IPS","R_IPS"],
    "LMB":  ["L_Amy","R_Amy","L_Thal","R_Thal"],
    "SUB":  ["L_Caudate","R_Caudate","Brainstem","L_Cerebellum","R_Cerebellum"],
}

SEQ_PATTERNS = {
    "bold": ["epi_bold","bold","rest","rsfmri","func","fmri","epi"],
    "t1":   ["t1_","mprage","t1w","gre_fsp","t1gre","irfse"],
    "dwi":  ["hardi","dti","dwi","diffusion","ep2d_diff"],
    "t2":   ["t2_","fse","tse","t2w"],
    "qsm":  ["qsm","swi","gre_field"],
    "mra":  ["tof","mra","angio"],
}


class BrainAnalyzer:
    """完整 fMRI 分析引擎 — 从 DICOM 到报告"""

    def __init__(self, dicom_path: str, output_dir: str, progress_cb=None,
                 fmriprep_dir: str = None):
        self.dicom_root  = dicom_path
        self.output_dir  = output_dir
        self.progress_cb = progress_cb or (lambda p, m: print(f"[{p:3d}%] {m}"))
        # 当提供 fMRIPrep derivatives 目录时，跳过 DICOM 转换与内置预处理
        self.fmriprep_dir = fmriprep_dir

        self.nifti_dir   = os.path.join(output_dir, "nifti")
        self.results_dir = os.path.join(output_dir, "results")
        self.plots_dir   = os.path.join(output_dir, "plots")
        self.report_imgs = os.path.join(output_dir, "report_imgs")
        self.reports_dir = os.path.join(output_dir, "reports")
        for d in [self.nifti_dir, self.results_dir, self.plots_dir,
                  self.report_imgs, self.reports_dir]:
            os.makedirs(d, exist_ok=True)

        self.scan_params:  dict = {}
        self.TR:           float = 2.0
        self.slice_timing: list  = []

        if self.fmriprep_dir:
            # fMRIPrep 模式：无需 DICOM，序列检测跳过
            self.progress_cb(1, "fMRIPrep 模式：使用预处理好的 derivatives...")
            self.sequences   = {}
            self.bold_folder = None
        else:
            self.progress_cb(1, "自动识别序列...")
            self.sequences   = self._detect_sequences()
            self.bold_folder = self.sequences.get("bold")
            if not self.bold_folder:
                raise RuntimeError("未找到 fMRI BOLD 序列。")
            self.progress_cb(3, f"识别 BOLD 序列: {os.path.basename(self.bold_folder)}")

    # ── 序列检测 ──────────────────────────────────────────────────────────────

    def _count_dicoms(self, folder: str) -> int:
        try:
            files = os.listdir(folder)
        except Exception:
            return 0
        return sum(1 for f in files
                   if f.endswith(".dcm") or
                   (not "." in f and os.path.isfile(os.path.join(folder, f))))

    def _detect_sequences(self) -> dict:
        root = self.dicom_root
        if self._count_dicoms(root) > 50:
            return {"bold": root}

        candidates: dict = {}
        try:
            subdirs = [d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d)) and not d.startswith(".")]
        except Exception:
            subdirs = []

        for sub in subdirs:
            full = os.path.join(root, sub)
            n    = self._count_dicoms(full)
            if n < 1:
                continue
            name_lower = sub.lower()
            matched = False
            for seq_type, keywords in SEQ_PATTERNS.items():
                for kw in keywords:
                    if kw in name_lower:
                        candidates.setdefault(seq_type, []).append((n, full))
                        matched = True
                        break
                if matched:
                    break

        seqs: dict = {}
        for seq_type, cands in candidates.items():
            cands.sort(reverse=True)
            best_n, best_path = cands[0]
            if seq_type == "bold" and best_n < 50:
                continue
            seqs[seq_type] = best_path

        if "bold" not in seqs:
            all_cands = sorted(
                [(self._count_dicoms(os.path.join(root, s)), os.path.join(root, s))
                 for s in subdirs], reverse=True)
            if all_cands and all_cands[0][0] > 100:
                seqs["bold"] = all_cands[0][1]

        return seqs

    # ── dcm2niix 转换 ─────────────────────────────────────────────────────────

    def _find_dcm2niix(self) -> str:
        for p in ["/opt/homebrew/bin/dcm2niix", "/usr/local/bin/dcm2niix",
                  shutil.which("dcm2niix") or ""]:
            if p and os.path.isfile(p):
                return p
        raise RuntimeError("找不到 dcm2niix。请安装: brew install dcm2niix")

    def convert_dicom_to_nifti(self) -> tuple:
        self.progress_cb(8, "DICOM → NIfTI (dcm2niix)...")
        dcm2niix = self._find_dcm2niix()
        cmd = [dcm2niix, "-z", "y", "-b", "y", "-f", "bold",
               "-o", self.nifti_dir, self.bold_folder]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"dcm2niix 失败:\n{result.stderr[:500]}")

        nifti_files = sorted(glob.glob(os.path.join(self.nifti_dir, "*.nii.gz")))
        if not nifti_files:
            raise RuntimeError("dcm2niix 未生成 NIfTI 文件。")

        nifti_path = nifti_files[0]
        for f in nifti_files:
            img = nib.load(f)
            if img.ndim == 4 and img.shape[3] > 50:
                nifti_path = f; break

        json_path = nifti_path.replace(".nii.gz", ".json")
        sidecar = {}
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8", errors="replace") as fh:
                sidecar = json.load(fh)
            self.TR            = float(sidecar.get("RepetitionTime", 2.0))
            self.slice_timing  = sidecar.get("SliceTiming", [])

        self._extract_scan_params(sidecar)
        img = nib.load(nifti_path)
        self.progress_cb(12, f"转换完成: {img.shape}, TR={self.TR}s")
        return nifti_path, sidecar

    def _extract_scan_params(self, sidecar: dict):
        dcm_files = sorted(glob.glob(os.path.join(self.bold_folder, "*.dcm")))
        if not dcm_files:
            dcm_files = sorted(glob.glob(os.path.join(self.bold_folder, "*")))
            dcm_files = [f for f in dcm_files if os.path.isfile(f) and not f.endswith(".DS_Store")]

        subject_id = age = sex = scan_date = institution = scanner = "N/A"
        if dcm_files:
            try:
                ds = pydicom.dcmread(dcm_files[0], stop_before_pixels=True, force=True)
                subject_id  = str(getattr(ds, "PatientID",              "unknown"))
                age         = str(getattr(ds, "PatientAge",             "N/A"))
                sex         = str(getattr(ds, "PatientSex",             "N/A"))
                scan_date   = str(getattr(ds, "StudyDate",              "N/A"))
                institution = str(getattr(ds, "InstitutionName",        "N/A"))
                scanner     = f"{getattr(ds,'Manufacturer','')} {getattr(ds,'ManufacturerModelName','')}"
            except Exception:
                pass

        te_raw = sidecar.get("EchoTime", 0)
        self.scan_params = {
            "subject_id":  subject_id,
            "age":         age,
            "sex":         sex,
            "scan_date":   scan_date,
            "institution": institution,
            "scanner":     scanner.strip(),
            "TR":          self.TR,
            "TE":          float(te_raw) * 1000 if te_raw < 1 else float(te_raw),
            "flip_angle":  float(sidecar.get("FlipAngle", 0)),
            "voxel_size":  sidecar.get("SliceThickness", "N/A"),
            "matrix":      f"{sidecar.get('AcquisitionMatrixPE','?')}",
            "phase_dir":   sidecar.get("PhaseEncodingDirection", "N/A"),
            "slice_timing_available": len(self.slice_timing) > 0,
        }
        with open(os.path.join(self.results_dir, "scan_parameters.json"),
                  "w", encoding="utf-8") as f:
            json.dump(self.scan_params, f, indent=2, ensure_ascii=False)

    # ── 预处理 ────────────────────────────────────────────────────────────────

    def preprocess(self, nifti_path: str, n_discard: int = 5) -> str:
        self.progress_cb(15, "加载数据...")
        img  = nib.load(nifti_path)
        data = img.get_fdata(dtype=np.float32)
        if data.ndim != 4:
            raise RuntimeError(f"数据不是4D: {data.shape}")
        nx, ny, nz, nt = data.shape

        # 1. 丢弃前几个 TR
        if nt > n_discard + 30:
            data = data[:, :, :, n_discard:]
            nt   = data.shape[3]
        self.progress_cb(17, f"丢弃前{n_discard}个TR → {nt}个时间点")

        # 2. 切片时间校正
        if self.slice_timing and len(self.slice_timing) == nz:
            self.progress_cb(20, "切片时间校正 (STC)...")
            data = self._stc(data, np.array(self.slice_timing), self.TR)
        else:
            self.progress_cb(20, "切片时间校正：跳过")

        # 3. 脑掩码
        self.progress_cb(23, "生成脑掩码...")
        brain_mean = data.mean(axis=3)
        nonzero    = brain_mean[brain_mean > 0]
        if len(nonzero) == 0:
            raise RuntimeError("数据全零，DICOM转换可能失败")
        thresh = np.percentile(nonzero, 65)
        mask   = brain_mean > thresh
        mask   = ndimage.binary_fill_holes(mask)
        mask   = ndimage.binary_erosion(mask, iterations=1)
        mask   = ndimage.binary_dilation(mask, iterations=1)
        n_vox  = int(mask.sum())
        self.progress_cb(25, f"脑掩码: {n_vox} 体素 ({100*n_vox/(nx*ny*nz):.1f}%)")
        np.save(os.path.join(self.results_dir, "brain_mask.npy"), mask)

        # 提取脑体素时间序列
        brain_ts = data[mask]  # (N_vox, nt)
        np.save(os.path.join(self.results_dir, "ts_raw_brain.npy"), brain_ts)

        # 4. PSC 标准化
        ts_mean = brain_ts.mean(axis=1, keepdims=True)
        ts_psc  = (brain_ts - ts_mean) / (np.abs(ts_mean) + 1e-6) * 100

        # 5. 线性去趋势
        t_vec = np.arange(nt, dtype=np.float64)
        X     = np.column_stack([np.ones(nt), t_vec])
        beta  = np.linalg.lstsq(X, ts_psc.T, rcond=None)[0]
        ts_det = ts_psc - (X @ beta).T

        # 6. 带通滤波 0.01–0.1 Hz
        self.progress_cb(30, "带通滤波 0.01–0.1 Hz...")
        fs = 1.0 / self.TR
        b, a   = signal.butter(4, [0.01/(fs/2), 0.1/(fs/2)], btype="band")
        ts_bp  = signal.filtfilt(b, a, ts_det, axis=1)

        # 7. 空间平滑 FWHM=6mm
        self.progress_cb(33, "空间平滑 FWHM=6mm...")
        vox_size     = float(img.header.get_zooms()[0])
        sigma        = 6.0 / (2.355 * vox_size)
        data_smooth  = np.zeros((nx, ny, nz, nt), dtype=np.float32)
        tmp          = np.zeros((nx, ny, nz), dtype=np.float32)
        for t in range(nt):
            tmp[:] = 0
            tmp[mask] = ts_bp[:, t].astype(np.float32)
            data_smooth[:, :, :, t] = gaussian_filter(tmp, sigma=sigma)

        np.save(os.path.join(self.results_dir, "data_preprocessed.npy"), data_smooth)
        np.save(os.path.join(self.results_dir, "ts_preprocessed.npy"),   data_smooth[mask])

        out_path = os.path.join(self.nifti_dir, "preprocessed_bold.nii.gz")
        nib.save(nib.Nifti1Image(data_smooth, img.affine, img.header), out_path)
        self.progress_cb(38, "预处理完成")
        return out_path

    @staticmethod
    def _stc(data: np.ndarray, slice_times: np.ndarray, TR: float) -> np.ndarray:
        """线性插值切片时间校正（参考时间 = TR/2）"""
        nx, ny, nz, nt = data.shape
        ref_time   = TR / 2.0
        t_axis     = np.arange(nt) * TR
        corrected  = data.copy()
        for z in range(nz):
            delta   = ref_time - float(slice_times[z])
            t_new   = t_axis - delta
            slab    = data[:, :, z, :].reshape(-1, nt)
            for i in range(slab.shape[0]):
                corrected[:, :, z, :].reshape(-1, nt)[i] = np.interp(
                    t_axis, t_new, slab[i],
                    left=slab[i, 0], right=slab[i, -1])
        return corrected

    # ── QC ───────────────────────────────────────────────────────────────────

    def quality_control(self, preprocessed_path: str) -> dict:
        self.progress_cb(40, "质量控制分析...")
        ts_raw = np.load(os.path.join(self.results_dir, "ts_raw_brain.npy"))
        mask   = np.load(os.path.join(self.results_dir, "brain_mask.npy"))
        nt     = ts_raw.shape[1]
        nx_, ny_, nz_ = mask.shape

        diff_sq   = np.diff(ts_raw, axis=1) ** 2
        DVARS     = np.sqrt(diff_sq.mean(axis=0))
        DVARS     = np.concatenate([[0], DVARS])
        DVARS_pct = DVARS / (ts_raw.mean() + 1e-8) * 100

        tsnr_vox  = ts_raw.mean(axis=1) / (ts_raw.std(axis=1) + 1e-8)
        tsnr_med  = float(np.median(tsnr_vox))
        tsnr_mean = float(tsnr_vox.mean())

        gs           = ts_raw.mean(axis=0)
        FD_proxy_pct = np.abs(np.diff(gs)) / (np.abs(gs[:-1]) + 1e-8) * 100
        FD_proxy_pct = np.concatenate([[0], FD_proxy_pct])

        dvars_thresh = DVARS_pct[1:].mean() + 2 * DVARS_pct[1:].std()
        bad_TPs      = np.where(DVARS_pct > dvars_thresh)[0]
        pct_bad      = float(100 * len(bad_TPs) / nt)

        score = 100
        if tsnr_med  < 30:  score -= 20
        elif tsnr_med < 60: score -= 10
        if pct_bad   > 20:  score -= 20
        elif pct_bad > 10:  score -= 10
        if nt        < 150: score -= 15
        score = max(0, score)
        stars = "★" * round(score/20) + "☆" * (5 - round(score/20))

        n_vox = int(mask.sum())
        qc = {
            "n_timepoints":        int(nt),
            "n_voxels_brain":      n_vox,
            "brain_coverage_pct":  float(100 * n_vox / (nx_*ny_*nz_)),
            "TR_s":                self.TR,
            "total_duration_min":  float(nt * self.TR / 60),
            "DVARS_pct_median":    float(np.median(DVARS_pct[1:])),
            "DVARS_pct_mean":      float(DVARS_pct[1:].mean()),
            "FD_proxy_pct_median": float(np.median(FD_proxy_pct[1:])),
            "FD_proxy_pct_mean":   float(FD_proxy_pct[1:].mean()),
            "tSNR_median":         tsnr_med,
            "tSNR_mean":           tsnr_mean,
            "tSNR_std":            float(tsnr_vox.std()),
            "n_bad_TPs":           int(len(bad_TPs)),
            "pct_bad_TPs":         pct_bad,
            "bad_TPs":             bad_TPs.tolist(),
            "QC_score":            score,
            "QC_stars":            stars,
            "usable_for_research": score >= 60,
            # backward-compat
            "score":               score,
            "mean_fd":             float(FD_proxy_pct[1:].mean()),
            "tsnr_median":         tsnr_med,
            "high_motion_pct":     pct_bad,
        }
        np.save(os.path.join(self.results_dir, "DVARS.npy"),      DVARS_pct)
        np.save(os.path.join(self.results_dir, "FD_proxy.npy"),   FD_proxy_pct)
        np.save(os.path.join(self.results_dir, "tSNR_voxels.npy"),tsnr_vox)
        np.save(os.path.join(self.results_dir, "tSNR.npy"),       tsnr_vox)
        with open(os.path.join(self.results_dir, "qc_metrics.json"),
                  "w", encoding="utf-8") as f:
            json.dump(qc, f, indent=2, ensure_ascii=False)
        self.progress_cb(45, f"QC: {score}/100 {stars}  tSNR={tsnr_med:.0f}  运动TP={pct_bad:.1f}%")
        return qc

    # ── 功能连接 ──────────────────────────────────────────────────────────────

    def compute_functional_connectivity(self, preprocessed_path: str) -> dict:
        self.progress_cb(48, "提取 ROI 时间序列...")
        data_smooth = np.load(os.path.join(self.results_dir, "data_preprocessed.npy"))
        img         = nib.load(preprocessed_path)
        affine_inv  = np.linalg.inv(img.affine)
        nx_, ny_, nz_, nt = data_smooth.shape

        roi_names = list(ROI_DEFS.keys())
        n_roi     = len(roi_names)
        roi_ts    = np.zeros((n_roi, nt), dtype=np.float32)

        for i, (name, mni) in enumerate(ROI_DEFS.items()):
            c = np.array([*mni, 1.0])
            v = affine_inv @ c
            cx, cy, cz = tuple(np.round(v[:3]).astype(int))
            r  = 1
            x0, x1 = max(0, cx-r), min(nx_-1, cx+r+1)
            y0, y1 = max(0, cy-r), min(ny_-1, cy+r+1)
            z0, z1 = max(0, cz-r), min(nz_-1, cz+r+1)
            patch   = data_smooth[x0:x1, y0:y1, z0:z1, :]
            if patch.size > 0:
                roi_ts[i] = patch.reshape(-1, nt).mean(axis=0)

        FC   = np.corrcoef(roi_ts)
        FC_z = np.arctanh(np.clip(FC, -0.9999, 0.9999))
        np.fill_diagonal(FC,   0); np.fill_diagonal(FC_z, 0)

        dmn_idx   = [roi_names.index(n) for n in NETWORKS["DMN"] if n in roi_names]
        FC_dmn    = FC[np.ix_(dmn_idx, dmn_idx)]
        dmn_fc    = float(FC_dmn[np.triu_indices(len(dmn_idx), k=1)].mean())

        net_stats: dict = {}
        for net, rois in NETWORKS.items():
            idx   = [roi_names.index(r) for r in rois if r in roi_names]
            sub   = FC[np.ix_(idx, idx)]
            upper = sub[np.triu_indices(len(idx), k=1)]
            net_stats[net] = {
                "n_rois":  len(idx),
                "mean_FC": float(upper.mean()) if len(upper)>0 else 0.0,
                "std_FC":  float(upper.std())  if len(upper)>0 else 0.0,
                "max_FC":  float(upper.max())  if len(upper)>0 else 0.0,
                "rois":    rois,
            }

        pcc_i   = roi_names.index("PCC")
        seed_fc = np.array([np.corrcoef(roi_ts[pcc_i], roi_ts[i])[0,1]
                             for i in range(n_roi)])

        np.save(os.path.join(self.results_dir, "FC_pearson.npy"),   FC)
        np.save(os.path.join(self.results_dir, "FC_fisherZ.npy"),   FC_z)
        np.save(os.path.join(self.results_dir, "roi_timeseries.npy"), roi_ts)
        with open(os.path.join(self.results_dir, "roi_names.json"), "w") as f:
            json.dump(roi_names, f)
        with open(os.path.join(self.results_dir, "network_stats.json"),
                  "w", encoding="utf-8") as f:
            json.dump(net_stats, f, indent=2, ensure_ascii=False)

        self.progress_cb(55, f"FC {n_roi}×{n_roi}  DMN={dmn_fc:.3f}")
        return {
            "matrix":        FC.tolist(),
            "labels":        roi_names,
            "dmn_mean_fc":   dmn_fc,
            "time_series":   roi_ts.tolist(),
            "network_stats": net_stats,
            "pcc_seed_fc":   dict(zip(roi_names, seed_fc.tolist())),
        }

    # ── ALFF / fALFF ─────────────────────────────────────────────────────────

    def compute_alff(self, preprocessed_path: str) -> dict:
        self.progress_cb(58, "计算 ALFF / fALFF...")
        mask        = np.load(os.path.join(self.results_dir, "brain_mask.npy"))
        data_smooth = np.load(os.path.join(self.results_dir, "data_preprocessed.npy"))
        img         = nib.load(preprocessed_path)
        nt          = data_smooth.shape[3]
        ts_raw      = np.load(os.path.join(self.results_dir, "ts_raw_brain.npy"))

        t_vec  = np.arange(nt, dtype=np.float64)
        X      = np.column_stack([np.ones(nt), t_vec])
        beta   = np.linalg.lstsq(X, ts_raw.T, rcond=None)[0]
        ts_det = ts_raw - (X @ beta).T

        freqs   = np.fft.rfftfreq(nt, d=self.TR)
        fft_amp = np.abs(np.fft.rfft(ts_det, axis=1))
        lo_idx  = np.where((freqs >= 0.01) & (freqs <= 0.1))[0]
        all_idx = np.where(freqs > 0)[0]

        ALFF  = fft_amp[:, lo_idx].mean(axis=1)
        fALFF = ALFF / (fft_amp[:, all_idx].mean(axis=1) + 1e-10)
        ALFF_z  = (ALFF  - ALFF.mean())  / (ALFF.std()  + 1e-10)
        fALFF_z = (fALFF - fALFF.mean()) / (fALFF.std() + 1e-10)

        alff_map  = np.zeros(data_smooth.shape[:3], dtype=np.float32)
        falff_map = np.zeros_like(alff_map)
        alff_map[mask]  = ALFF_z.astype(np.float32)
        falff_map[mask] = fALFF_z.astype(np.float32)

        np.save(os.path.join(self.results_dir, "ALFF_map.npy"),  alff_map)
        np.save(os.path.join(self.results_dir, "fALFF_map.npy"), falff_map)
        nib.save(nib.Nifti1Image(alff_map,  img.affine),
                 os.path.join(self.results_dir, "alff_z.nii.gz"))
        nib.save(nib.Nifti1Image(falff_map, img.affine),
                 os.path.join(self.results_dir, "falff_z.nii.gz"))
        self.progress_cb(62, f"ALFF_z={alff_map[mask].mean():.3f}")
        return {"alff_mean": float(alff_map[mask].mean()),
                "falff_mean": float(falff_map[mask].mean())}

    # ── ReHo ─────────────────────────────────────────────────────────────────

    def compute_reho(self, preprocessed_path: str) -> dict:
        self.progress_cb(63, "计算 ReHo（Kendall's W）...")
        mask        = np.load(os.path.join(self.results_dir, "brain_mask.npy"))
        data_smooth = np.load(os.path.join(self.results_dir, "data_preprocessed.npy"))
        img         = nib.load(preprocessed_path)
        nx_, ny_, nz_, nt = data_smooth.shape
        ts_raw = np.load(os.path.join(self.results_dir, "ts_raw_brain.npy"))

        t_vec  = np.arange(nt, dtype=np.float64)
        X      = np.column_stack([np.ones(nt), t_vec])
        beta   = np.linalg.lstsq(X, ts_raw.T, rcond=None)[0]
        ts_det = ts_raw - (X @ beta).T

        ts_4d  = np.zeros((nx_, ny_, nz_, nt), dtype=np.float32)
        ts_4d[mask] = ts_det.astype(np.float32)

        reho_map    = np.zeros((nx_, ny_, nz_), dtype=np.float32)
        mask_coords = np.array(np.where(mask)).T
        total       = len(mask_coords)
        for idx_, (cx, cy, cz) in enumerate(mask_coords):
            x0, x1 = max(0, cx-1), min(nx_, cx+2)
            y0, y1 = max(0, cy-1), min(ny_, cy+2)
            z0, z1 = max(0, cz-1), min(nz_, cz+2)
            patch  = ts_4d[x0:x1, y0:y1, z0:z1, :]
            k_ts   = patch.reshape(-1, nt)
            m      = mask[x0:x1, y0:y1, z0:z1].reshape(-1)
            k_ts   = k_ts[m]; k = k_ts.shape[0]
            if k < 2: continue
            ranks  = np.apply_along_axis(rankdata, 1, k_ts)
            Ri     = ranks.sum(axis=0)
            S      = ((Ri - Ri.mean()) ** 2).sum()
            W      = 12 * S / (k**2 * (nt**3 - nt))
            reho_map[cx, cy, cz] = float(W)
            if idx_ % 5000 == 0:
                pct = 63 + int(5 * idx_ / total)
                self.progress_cb(pct, f"ReHo {idx_}/{total}...")

        reho_z = np.zeros_like(reho_map)
        br     = reho_map[mask]
        reho_z[mask] = ((br - br.mean()) / (br.std() + 1e-10)).astype(np.float32)

        np.save(os.path.join(self.results_dir, "ReHo_map.npy"), reho_z)
        nib.save(nib.Nifti1Image(reho_z, img.affine),
                 os.path.join(self.results_dir, "reho_z.nii.gz"))
        self.progress_cb(68, f"ReHo_z={reho_z[mask].mean():.3f}")
        return {"reho_mean": float(reho_z[mask].mean())}

    # ── 图论分析 ──────────────────────────────────────────────────────────────

    def graph_theory_analysis(self, fc_results: dict) -> dict:
        self.progress_cb(70, "图论分析 (networkx)...")
        import networkx as nx

        roi_names = list(ROI_DEFS.keys())
        n_roi     = len(roi_names)
        FC        = np.array(fc_results["matrix"])
        if FC.shape[0] < 2:
            return self._graph_defaults(n_roi, roi_names)

        thresh  = 0.2
        G_bin   = nx.from_numpy_array((FC > thresh).astype(float))
        nx.set_node_attributes(G_bin, {i: roi_names[i] for i in range(n_roi)}, "label")

        degree  = dict(G_bin.degree())
        deg_arr = np.array([degree[i] for i in range(n_roi)])
        bc      = nx.betweenness_centrality(G_bin, normalized=True)
        cc      = nx.clustering(G_bin)
        try:   ec = nx.eigenvector_centrality(G_bin, max_iter=500)
        except: ec = {i: 0.0 for i in range(n_roi)}

        try:
            char_path = nx.average_shortest_path_length(G_bin)
        except Exception:
            try:
                Gc = G_bin.subgraph(max(nx.connected_components(G_bin), key=len))
                char_path = nx.average_shortest_path_length(Gc)
            except Exception:
                char_path = float("inf")

        glob_eff  = nx.global_efficiency(G_bin)
        local_eff = nx.local_efficiency(G_bin)
        try:
            mod_res    = list(nx.community.greedy_modularity_communities(G_bin))
            modularity = nx.community.modularity(G_bin, mod_res)
            n_comm     = len(mod_res)
        except Exception:
            mod_res = []; modularity = 0.0; n_comm = 0
        avg_cc   = nx.average_clustering(G_bin)

        mean_deg = deg_arr.mean()
        Lr = np.log(max(n_roi,2)) / np.log(max(mean_deg,2))
        Cr = mean_deg / n_roi
        if char_path > 0 and not np.isinf(char_path) and Lr > 0 and Cr > 0:
            sigma = (avg_cc / Cr) / (char_path / Lr)
        else:
            sigma = 0.0

        hub_thresh_deg = np.percentile(deg_arr, 75)
        hub_thresh_bc  = np.percentile(list(bc.values()), 75)
        hubs = [roi_names[i] for i in range(n_roi)
                if deg_arr[i] >= hub_thresh_deg and bc[i] >= hub_thresh_bc]

        communities = {n: i for i, comm in enumerate(mod_res) for n in comm} if mod_res else {}
        part_coeff: dict = {}
        for v in G_bin.nodes():
            nbrs = list(G_bin.neighbors(v))
            if not nbrs: part_coeff[v] = 0.0; continue
            kv    = len(nbrs)
            cnt: dict = {}
            for u in nbrs: c = communities.get(u,0); cnt[c] = cnt.get(c,0)+1
            part_coeff[v] = 1 - sum((x/kv)**2 for x in cnt.values())

        gm = {
            "n_nodes":             n_roi,
            "n_edges":             int(G_bin.number_of_edges()),
            "density":             float(nx.density(G_bin)),
            "mean_degree":         float(mean_deg),
            "avg_clustering":      float(avg_cc),
            "global_efficiency":   float(glob_eff),
            "local_efficiency":    float(local_eff),
            "char_path_length":    float(char_path) if not np.isinf(char_path) else 999.0,
            "small_world_sigma":   float(sigma),
            "modularity":          float(modularity),
            "n_communities":       n_comm,
            "hub_regions":         hubs,
            "threshold_r":         thresh,
            # back-compat keys
            "clustering_coefficient": float(avg_cc),
            "path_length":         float(char_path) if not np.isinf(char_path) else 999.0,
            "small_worldness":     float(sigma),
            "degree":              deg_arr.tolist(),
            "per_node": {
                roi_names[i]: {
                    "degree":                  int(degree[i]),
                    "betweenness_centrality":  float(bc[i]),
                    "clustering_coefficient":  float(cc[i]),
                    "eigenvector_centrality":  float(ec[i]),
                    "participation_coefficient": float(part_coeff[i]),
                    "community":               int(communities.get(i, 0)),
                } for i in range(n_roi)
            },
        }
        with open(os.path.join(self.results_dir, "graph_metrics.json"),
                  "w", encoding="utf-8") as f:
            json.dump(gm, f, indent=2, ensure_ascii=False)
        self.progress_cb(74, f"图论 CC={avg_cc:.3f} GE={glob_eff:.3f} σ={sigma:.2f} "
                             f"Hubs={hubs}")
        return gm

    # ── 动态 FC ───────────────────────────────────────────────────────────────

    def dynamic_fc_analysis(self, fc_results: dict) -> dict:
        self.progress_cb(76, "动态功能连接 (Sliding Window)...")
        from sklearn.cluster import KMeans
        roi_ts    = np.load(os.path.join(self.results_dir, "roi_timeseries.npy"))
        roi_names = list(ROI_DEFS.keys())
        nt        = roi_ts.shape[1]
        dmn_idx   = [roi_names.index(n) for n in NETWORKS["DMN"] if n in roi_names]
        dmn_ts    = roi_ts[dmn_idx]
        win_size  = 44; step = 4
        windows   = list(range(0, nt - win_size, step))
        n_win     = len(windows)
        if n_win < 4:
            self.progress_cb(78, "时间点不足，跳过动态FC")
            return {"n_windows":0, "mean_variability":0.0}
        dFC_list = []
        for w in windows:
            seg  = dmn_ts[:, w:w+win_size]
            corr = np.corrcoef(seg); np.fill_diagonal(corr, 0)
            dFC_list.append(corr[np.triu_indices(len(dmn_idx), k=1)])
        dFC_mat = np.array(dFC_list)
        states  = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(dFC_mat)
        s_count = np.bincount(states, minlength=2)
        transitions = int(np.sum(np.diff(states) != 0))
        dfc = {
            "n_windows":        n_win,
            "window_size_TPs":  win_size,
            "window_size_s":    win_size * self.TR,
            "step_TPs":         step,
            "n_states":         2,
            "dwell_times_s":    {f"State_{i+1}": float(s_count[i]*step*self.TR) for i in range(2)},
            "state_occupancy":  {f"State_{i+1}": float(s_count[i]/n_win) for i in range(2)},
            "n_transitions":    transitions,
            "mean_FC_per_window": dFC_mat.mean(axis=1).tolist(),
            "std_FC_per_window":  dFC_mat.std(axis=1).tolist(),
            "state_labels":     states.tolist(),
            "mean_variability": float(np.std(dFC_mat, axis=0).mean()),
        }
        np.save(os.path.join(self.results_dir, "dFC_matrix.npy"), dFC_mat)
        np.save(os.path.join(self.results_dir, "dFC_states.npy"), states)
        with open(os.path.join(self.results_dir, "dFC_results.json"), "w") as f:
            json.dump(dfc, f, ensure_ascii=False, indent=2)
        self.progress_cb(79, f"动态FC: {n_win}窗口 转换={transitions}次")
        return dfc

    def brain_fingerprint(self, fc_results, graph_results, qc_results) -> dict:
        roi_names = list(ROI_DEFS.keys()); n_roi = len(roi_names)
        FC       = np.array(fc_results["matrix"])
        fc_upper = FC[np.triu_indices(n_roi, k=1)]
        ns       = fc_results.get("network_stats", {})
        fp = {
            "fc_vector_length": len(fc_upper),
            "fc_mean":          float(fc_upper.mean()),
            "fc_std":           float(fc_upper.std()),
            "fc_positive_pct":  float((fc_upper>0).sum()/len(fc_upper)*100),
            "fc_strong_pct":    float((fc_upper>0.3).sum()/len(fc_upper)*100),
            "dmn_strength":     fc_results.get("dmn_mean_fc",0.0),
            "network_fc":       {net: v["mean_FC"] for net, v in ns.items()},
        }
        sm = {
            "FC_matrix_shape": [n_roi, n_roi],
            "FC_mean":         float(FC[FC!=0].mean()) if FC[FC!=0].size>0 else 0.0,
            "FC_std":          float(FC[FC!=0].std())  if FC[FC!=0].size>0 else 0.0,
            "DMN_internal_FC": fc_results.get("dmn_mean_fc",0.0),
            "network_strength": {k: v["mean_FC"] for k,v in ns.items()},
            "graph_global":    {k: graph_results.get(k,0) for k in
                                ["mean_degree","avg_clustering","global_efficiency",
                                 "char_path_length","small_world_sigma","modularity","hub_regions"]},
        }
        np.save(os.path.join(self.results_dir, "fc_fingerprint_vector.npy"), fc_upper)
        with open(os.path.join(self.results_dir, "brain_fingerprint.json"),"w") as f:
            json.dump(fp, f, indent=2, ensure_ascii=False)
        with open(os.path.join(self.results_dir, "analysis_summary.json"),"w", encoding="utf-8") as f:
            json.dump(sm, f, indent=2, ensure_ascii=False)
        return fp

    # ── 报告图像 (Matplotlib PNG) ─────────────────────────────────────────────

    def generate_report_images(self, fc_results, qc_results, graph_results, dfc_results) -> list:
        self.progress_cb(82, "生成报告图像...")
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        roi_names = list(ROI_DEFS.keys()); n_roi = len(roi_names)
        FC = np.array(fc_results["matrix"]); TR = self.TR
        imgs = self.report_imgs; files = []

        def save(name):
            p = os.path.join(imgs, name)
            plt.savefig(p, dpi=150, bbox_inches="tight"); plt.close(); files.append(p)

        # 1. FC 矩阵
        fig, ax = plt.subplots(figsize=(8,7))
        im = ax.imshow(FC, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(n_roi)); ax.set_xticklabels(roi_names, rotation=90, fontsize=5.5)
        ax.set_yticks(range(n_roi)); ax.set_yticklabels(roi_names, fontsize=5.5)
        plt.colorbar(im, ax=ax); ax.set_title("FC Matrix (Pearson r)")
        plt.tight_layout(); save("fc_matrix.png")

        # 2. QC
        try:
            FD=np.load(os.path.join(self.results_dir,"FD_proxy.npy"))
            DVARS=np.load(os.path.join(self.results_dir,"DVARS.npy"))
            tSNR=np.load(os.path.join(self.results_dir,"tSNR_voxels.npy"))
            t=np.arange(len(FD))*TR
            fig,axes=plt.subplots(3,1,figsize=(10,6))
            axes[0].plot(t,FD,color="#E74C3C",lw=0.8)
            axes[0].axhline(FD[1:].mean()+2*FD[1:].std(),ls="--",color="orange",lw=0.8)
            axes[0].set_ylabel("FD proxy (%)")
            axes[1].plot(t,DVARS,color="#3498DB",lw=0.8)
            axes[1].axhline(DVARS[1:].mean()+2*DVARS[1:].std(),ls="--",color="orange",lw=0.8)
            axes[1].set_ylabel("DVARS (%)")
            axes[2].hist(tSNR[tSNR<200],bins=50,color="#2ECC71",alpha=0.7)
            axes[2].axvline(np.median(tSNR[tSNR>0]),color="red",ls="--",lw=1)
            axes[2].set_xlabel("tSNR")
            fig.suptitle(f"QC {qc_results['QC_score']}/100 {qc_results['QC_stars']}")
            plt.tight_layout(); save("qc_timeseries.png")
        except Exception as e: print(f"QC图警告: {e}")

        # 3. Brain maps
        try:
            mask=np.load(os.path.join(self.results_dir,"brain_mask.npy"))
            for mapname,fname,cmap in [("ALFF_map","alff_brain.png","hot"),
                                        ("fALFF_map","falff_brain.png","hot"),
                                        ("ReHo_map","reho_brain.png","RdYlBu_r")]:
                mp=os.path.join(self.results_dir,f"{mapname}.npy")
                if not os.path.exists(mp): continue
                mapdata=np.load(mp); nz_=mapdata.shape[2]
                fig,axes=plt.subplots(1,4,figsize=(14,3))
                for col,sl in enumerate([nz_//5,nz_//3,nz_//2,2*nz_//3]):
                    axes[col].imshow(mapdata[:,:,sl].T,cmap=cmap,origin="lower",
                                     vmin=np.percentile(mapdata[mask],1),
                                     vmax=np.percentile(mapdata[mask],99))
                    axes[col].set_title(f"Z={sl}"); axes[col].axis("off")
                fig.suptitle(mapname.replace("_map","")+" (z-score)")
                plt.tight_layout(); save(fname)
        except Exception as e: print(f"brain map图警告: {e}")

        # 4. 网络强度
        ns=fc_results.get("network_stats",{})
        nets=list(ns.keys()); vals=[ns[n]["mean_FC"] for n in nets]
        clrs=["#E74C3C","#F39C12","#3498DB","#2ECC71","#9B59B6","#1ABC9C","#E67E22","#95A5A6"]
        fig,ax=plt.subplots(figsize=(7,4))
        bars=ax.bar(nets,vals,color=clrs[:len(nets)],alpha=0.85)
        ax.axhline(0,color="black",lw=0.5)
        for bar,v in zip(bars,vals): ax.text(bar.get_x()+bar.get_width()/2,v+0.003,f"{v:.2f}",ha="center",fontsize=8)
        ax.set_ylabel("Mean Pearson r"); ax.set_title("Network FC Strength")
        plt.tight_layout(); save("network_strength.png")

        # 5. Hub
        deg=[graph_results["per_node"][n]["degree"] for n in roi_names]
        bc=[graph_results["per_node"][n]["betweenness_centrality"] for n in roi_names]
        hubs=graph_results.get("hub_regions",[])
        clr_h=["#E74C3C" if n in hubs else "#95A5A6" for n in roi_names]
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        axes[0].bar(range(n_roi),deg,color=clr_h,alpha=0.8)
        axes[0].set_xticks(range(n_roi)); axes[0].set_xticklabels(roi_names,rotation=90,fontsize=5.5)
        axes[0].set_ylabel("Degree"); axes[0].set_title("Node Degree (red=Hub)")
        axes[1].scatter(deg,bc,c=clr_h,s=60,alpha=0.8,zorder=5)
        for i,n in enumerate(roi_names):
            if n in hubs: axes[1].annotate(n,(deg[i],bc[i]),fontsize=6,xytext=(3,3),textcoords="offset points")
        axes[1].set_xlabel("Degree"); axes[1].set_ylabel("BC")
        plt.tight_layout(); save("graph_hubs.png")

        # 6. DMN 矩阵
        dmn_nodes=NETWORKS["DMN"]
        dmn_idx=[roi_names.index(n) for n in dmn_nodes if n in roi_names]
        FC_dmn=FC[np.ix_(dmn_idx,dmn_idx)]
        fig,ax=plt.subplots(figsize=(5,4.5))
        im=ax.imshow(FC_dmn,cmap="RdBu_r",vmin=-1,vmax=1)
        ax.set_xticks(range(len(dmn_nodes))); ax.set_xticklabels(dmn_nodes,rotation=45,ha="right",fontsize=8)
        ax.set_yticks(range(len(dmn_nodes))); ax.set_yticklabels(dmn_nodes,fontsize=8)
        for i in range(len(dmn_nodes)):
            for j in range(len(dmn_nodes)):
                ax.text(j,i,f"{FC_dmn[i,j]:.2f}",ha="center",va="center",fontsize=7,
                        color="white" if abs(FC_dmn[i,j])>0.5 else "black")
        plt.colorbar(im,ax=ax); ax.set_title("DMN Internal FC Matrix")
        plt.tight_layout(); save("dmn_fc.png")

        # 7. 动态 FC
        try:
            dFC_mat=np.load(os.path.join(self.results_dir,"dFC_matrix.npy"))
            dFC_st=np.load(os.path.join(self.results_dir,"dFC_states.npy"))
            fig,axes=plt.subplots(2,1,figsize=(10,5),gridspec_kw={"height_ratios":[3,1]})
            im=axes[0].imshow(dFC_mat.T,aspect="auto",cmap="RdBu_r",vmin=-1,vmax=1)
            axes[0].set_ylabel("DMN pairs"); axes[0].set_title("Dynamic FC (88s window)")
            plt.colorbar(im,ax=axes[0])
            axes[1].scatter(range(len(dFC_st)),dFC_st,c=["#E74C3C" if s==0 else "#3498DB" for s in dFC_st],s=15)
            axes[1].set_yticks([0,1]); axes[1].set_xlabel("Window")
            plt.tight_layout(); save("dynamic_fc.png")
        except Exception as e: print(f"动态FC图警告: {e}")

        # 8. ROI 时间序列
        try:
            roi_ts=np.load(os.path.join(self.results_dir,"roi_timeseries.npy"))
            key_rois=["mPFC","PCC","ACC_dACC","L_AI","L_dlPFC","L_Amy"]
            t_ax=np.arange(roi_ts.shape[1])*TR
            clrs_ts=["#E74C3C","#3498DB","#F39C12","#2ECC71","#9B59B6","#E67E22"]
            fig,axes=plt.subplots(len(key_rois),1,figsize=(12,7),sharex=True)
            for i,name in enumerate(key_rois):
                if name in roi_names:
                    ts=roi_ts[roi_names.index(name)]; tsz=(ts-ts.mean())/(ts.std()+1e-8)
                    axes[i].plot(t_ax,tsz,color=clrs_ts[i],lw=0.8)
                    axes[i].set_ylabel(name,fontsize=8)
                    axes[i].set_ylim(-4,4)
            axes[-1].set_xlabel("Time (s)")
            fig.suptitle("Key ROI Time Series (z-score)")
            plt.tight_layout(); save("roi_timeseries.png")
        except Exception as e: print(f"ROI TS图警告: {e}")

        self.progress_cb(85, f"报告图像: {len(files)} 张")
        return files

    # ── 一键运行主管线 ────────────────────────────────────────────────────────

    def run_full_pipeline(self, options: dict) -> dict:
        results: dict = {}
        try:
            # ── 管线配置快照 ────────────────────────────────────────────────
            from core.advanced_preprocessing import PipelineConfig
            cfg = PipelineConfig(self.output_dir, overrides={
                "nuisance_regression": {
                    "motion_params": 24 if options.get("motion_24") else 6,
                    "wm_regression": options.get("wm_csf", True),
                    "csf_regression": options.get("wm_csf", True),
                    "gsr": options.get("gsr", False),
                },
                "roi_system": {
                    "atlas": "schaefer_2018" if options.get("schaefer") else "mni_33roi",
                    "n_parcels": options.get("schaefer_n", 100),
                },
            })
            cfg.save_yaml()

            # ══ 输入分支：fMRIPrep 金标准数据 vs 内置管线 ══════════════════════
            fmriprep_mode = bool(getattr(self, "fmriprep_dir", None))
            motion_params = None
            fd_mm = None

            if fmriprep_mode:
                # ── 使用 fMRIPrep 预处理好的 derivatives（金标准）─────────────
                self.progress_cb(10, "检测到 fMRIPrep 数据，使用金标准预处理结果...")
                from core.fmriprep_loader import FMRIPrepLoader
                loader = FMRIPrepLoader(self.fmriprep_dir)
                subjects = loader.detect_subjects()
                if not subjects:
                    raise RuntimeError(f"fMRIPrep 目录未找到受试者: {self.fmriprep_dir}")
                subj = getattr(self, "fmriprep_subject", None) or subjects[0]
                files = loader.find_bold(subj)
                if not files.get("bold"):
                    raise RuntimeError(f"未找到 {subj} 的 preproc_bold（MNI 空间）")

                strategy = options.get("confound_strategy", "24P")
                pre = loader.clean_bold(files, self.results_dir,
                                        TR=self.TR, strategy=strategy,
                                        progress_cb=self.progress_cb)
                self.scan_params.update({
                    "subject_id": subj.replace("sub-", ""),
                    "preproc_backbone": "fMRIPrep (金标准)",
                    "confound_strategy": strategy,
                })
                results.update({"nifti_file": files["bold"],
                                "scan_params": self.scan_params,
                                "fmriprep_subject": subj,
                                "preproc_backbone": "fmriprep"})
                results["preprocessed"] = pre
                if files.get("confounds"):
                    try:
                        fd_mm = loader.get_fd(files["confounds"])
                        results["fd_mm"] = fd_mm.tolist()
                    except Exception as e:
                        self.progress_cb(12, f"FD 读取跳过: {e}")
            else:
                # ── 内置管线（无 fMRIPrep 时的兜底方案）──────────────────────
                nifti, sidecar = self.convert_dicom_to_nifti()
                results.update({"nifti_file": nifti, "scan_params": self.scan_params,
                                 "sidecar": sidecar,
                                 "preproc_backbone": "builtin"})

                # ── 基础预处理 ─────────────────────────────────────────────
                pre  = self.preprocess(nifti)
                results["preprocessed"] = pre

            # ── 运动估计（相位相关法）— 仅内置管线需要 ─────────────────────────
            if not fmriprep_mode and options.get("motion_correction", True):
                try:
                    self.progress_cb(35, "运动估计（相位相关法）...")
                    from core.advanced_preprocessing import MotionEstimator
                    img  = __import__("nibabel").load(nifti)
                    data = img.get_fdata(dtype=__import__("numpy").float32)
                    me   = MotionEstimator(data, self.TR, self.results_dir,
                                           progress_cb=self.progress_cb)
                    motion_params = me.estimate_translations()
                    fd_mm = __import__("numpy").load(
                        __import__("os").path.join(self.results_dir, "fd_mm.npy"))
                    results["motion_params"] = motion_params.tolist()
                    results["fd_mm"] = fd_mm.tolist()
                except Exception as e:
                    self.progress_cb(35, f"运动估计跳过: {e}")

            # ── Nuisance Regression ─────────────────────────────────────────
            if options.get("nuisance_regression", True):
                try:
                    self.progress_cb(37, "Nuisance regression...")
                    import numpy as np
                    from core.advanced_preprocessing import NuisanceRegressor
                    ts_raw = np.load(__import__("os").path.join(
                        self.results_dir, "ts_raw_brain.npy"))
                    mask   = np.load(__import__("os").path.join(
                        self.results_dir, "brain_mask.npy"))
                    nr = NuisanceRegressor(ts_raw, mask, self.results_dir)

                    # WM/CSF 信号提取（从 4D 平滑数据）
                    data_smooth = np.load(__import__("os").path.join(
                        self.results_dir, "data_preprocessed.npy"))
                    wm_csf = None
                    if options.get("wm_csf", True):
                        wm_csf = nr.extract_wm_csf_signals(data_smooth)

                    ts_clean = nr.regress(
                        motion_params=motion_params,
                        wm_csf_signals=wm_csf,
                        include_gsr=options.get("gsr", False),
                        n_motion_params=24 if options.get("motion_24") else 6,
                    )
                    results["nuisance_cleaned"] = True
                except Exception as e:
                    self.progress_cb(37, f"Nuisance regression 跳过: {e}")
                    results["nuisance_cleaned"] = False

            # ── QC ─────────────────────────────────────────────────────────
            qc   = self.quality_control(pre)
            results["qc_metrics"] = qc

            # ── Carpet Plot + Scrubbing ──────────────────────────────────────
            if options.get("carpet_plot", True):
                try:
                    self.progress_cb(46, "Carpet plot + scrubbing 建议...")
                    import numpy as np
                    from core.advanced_preprocessing import CarpetPlotQC
                    img_4d = __import__("nibabel").load(pre)
                    data_4d= img_4d.get_fdata(dtype=np.float32)
                    mask   = np.load(__import__("os").path.join(
                        self.results_dir, "brain_mask.npy"))
                    FD_arr = np.load(__import__("os").path.join(
                        self.results_dir, "FD_proxy.npy"))
                    DVARS  = np.load(__import__("os").path.join(
                        self.results_dir, "DVARS.npy"))
                    cpqc   = CarpetPlotQC(data_4d, mask, FD_arr, DVARS,
                                           self.TR, self.results_dir)
                    scrub  = cpqc.recommend_scrubbing()
                    carpet = cpqc.generate_carpet_plot()
                    results["scrubbing"]   = scrub
                    results["carpet_plot"] = carpet
                    self.progress_cb(47, f"Scrubbing建议: 去除{scrub['n_scrubbed']}帧"
                                        f" → 剩余{scrub['n_remaining']}帧")
                except Exception as e:
                    self.progress_cb(46, f"Carpet plot 跳过: {e}")

            # ── FC (Schaefer 或 MNI-33 ROI) ────────────────────────────────
            if options.get("schaefer", False):
                try:
                    self.progress_cb(50, f"Schaefer-{options.get('schaefer_n',100)} FC...")
                    from core.advanced_preprocessing import AtlasROIExtractor
                    ext = AtlasROIExtractor(
                        n_rois=options.get("schaefer_n", 100),
                        output_dir=self.results_dir)
                    ts_s, lbl_s, net_s = ext.extract_timeseries(pre)
                    if ts_s is not None:
                        FC_s = ext.compute_fc_matrix(ts_s)
                        ns_s = ext.network_stats(FC_s, net_s)
                        results["fc_schaefer"] = {
                            "n_rois":        options.get("schaefer_n", 100),
                            "network_stats": ns_s,
                            "matrix_file":   f"schaefer{options.get('schaefer_n',100)}_FC_pearson.npy",
                        }
                        self.progress_cb(55, f"Schaefer FC 完成 {FC_s.shape[0]}×{FC_s.shape[0]}")
                except Exception as e:
                    self.progress_cb(50, f"Schaefer FC 跳过: {e}")

            # 始终运行 MNI-33 ROI FC（作为基础结果）
            fc   = self.compute_functional_connectivity(pre)
            results["fc"] = fc
            if options.get("alff", True):
                results["alff"] = self.compute_alff(pre)
            if options.get("reho", True):
                results["reho"] = self.compute_reho(pre)
            else:
                results["reho"] = {"reho_mean": 0.0}
            graph = self.graph_theory_analysis(fc)
            results["graph"] = graph
            if options.get("dynamic", True):
                results["dynamic"] = self.dynamic_fc_analysis(fc)
            else:
                results["dynamic"] = {"n_windows": 0, "mean_variability": 0.0}
            results["fingerprint"] = self.brain_fingerprint(fc, graph, qc)
            results["report_images"] = self.generate_report_images(
                fc, qc, graph, results["dynamic"])

            # ── 多模态分析（T1 / DTI / QSM）──────────────────────────────────
            mm_seqs = {k: v for k, v in self.sequences.items()
                       if k in ("t1", "dwi", "qsm")}
            if mm_seqs:
                self.progress_cb(86, f"多模态分析: {list(mm_seqs.keys())}...")
                try:
                    from core.multimodal_analyzer import MultimodalAnalyzer
                    mma = MultimodalAnalyzer(
                        self.dicom_root, self.output_dir, progress_cb=self.progress_cb)
                    results["multimodal"] = mma.run_all_multimodal(mm_seqs)
                except Exception as e:
                    print(f"多模态分析警告（不影响主报告）: {e}")
                    results["multimodal"] = {}
            else:
                results["multimodal"] = {}
            if options.get("pdf") or options.get("word"):
                self.progress_cb(90, "生成报告文档...")
                from core.report_generator import ReportGenerator
                rg = ReportGenerator(results, self.output_dir,
                                     scan_params=self.scan_params,
                                     update_literature=options.get("update_literature", False))
                reports: dict = {}
                if options.get("pdf"):
                    reports["pdf"] = rg.generate_pdf_report("zh")
                    if options.get("bilingual"):
                        reports["pdf_en"] = rg.generate_pdf_report("en")
                if options.get("word"):
                    reports["word"] = rg.generate_word_report("zh")
                    if options.get("bilingual"):
                        reports["word_en"] = rg.generate_word_report("en")
                results["reports"] = reports

            # ── 可重复性哈希 + 管线快照 ──────────────────────────────────────
            self.progress_cb(99, "生成可重复性哈希...")
            try:
                from core.advanced_preprocessing import PipelineConfig
                cfg2 = PipelineConfig(self.output_dir)
                snap = cfg2.snapshot(additional_info={
                    "subject_id": self.scan_params.get("subject_id","unknown"),
                    "bold_shape":  str(results.get("sidecar",{}).get("RepetitionTime","?")),
                    "n_sequences": len(self.sequences),
                })
                hashes = cfg2.compute_reproducibility_hash(
                    nifti_path=results.get("nifti_file"),
                    results_dir=self.results_dir)
                results["reproducibility"] = {
                    "config_hash":    hashes.get("config_hash",""),
                    "results_hash":   hashes.get("results_hash",""),
                    "pipeline_snap":  snap,
                }
            except Exception as e:
                print(f"可重复性哈希跳过: {e}")
                results["reproducibility"] = {}

            self.progress_cb(100, "✓ 全部分析完成！")
        except Exception as e:
            import traceback
            raise RuntimeError(f"{str(e)}\n\n{traceback.format_exc()}") from e
        return results

    def _graph_defaults(self, n_roi, roi_names):
        d = {
            "n_nodes": n_roi, "n_edges":0, "density":0.0, "mean_degree":0.0,
            "avg_clustering":0.0, "global_efficiency":0.0, "local_efficiency":0.0,
            "char_path_length":0.0, "small_world_sigma":0.0, "modularity":0.0,
            "n_communities":0, "hub_regions":[], "threshold_r":0.2,
            "clustering_coefficient":0.0, "path_length":0.0,
            "small_worldness":0.0, "degree":[0]*n_roi,
            "per_node":{n: {"degree":0,"betweenness_centrality":0.0,
                             "clustering_coefficient":0.0,"eigenvector_centrality":0.0,
                             "participation_coefficient":0.0,"community":0}
                        for n in roi_names},
        }
        return d
