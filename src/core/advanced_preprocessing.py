#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级预处理模块 v1.0
包含: nuisance regression / carpet plot / scrubbing /
      Schaefer atlas ROI / 配置快照 / 可重复性哈希
"""
import os, json, hashlib, warnings, glob
import numpy as np
import nibabel as nib
from scipy import signal, ndimage
from scipy.ndimage import gaussian_filter
from sklearn.decomposition import PCA
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# 1. NUISANCE REGRESSION
# ─────────────────────────────────────────────────────────────────────────────

class NuisanceRegressor:
    """
    标准 nuisance regression 管线：
      - 6/24 运动参数（平移 + 旋转 + 其平方 + 其一阶导数）
      - WM + CSF 信号回归
      - 全局信号回归（可选，默认关闭）
    """

    def __init__(self, ts_brain: np.ndarray, mask: np.ndarray,
                 output_dir: str):
        """
        ts_brain : (N_vox, nt)  已预处理时间序列
        mask     : (nx, ny, nz)  脑掩码
        """
        self.ts     = ts_brain      # (N_vox, nt)
        self.mask   = mask
        self.out    = output_dir
        self.nt     = ts_brain.shape[1]

    # ── 运动参数 ──────────────────────────────────────────────────────────────
    def load_motion_params(self, motion_file: str) -> np.ndarray:
        """
        读取运动参数文件（列：tx ty tz rx ry rz）。
        支持 FSL mcflirt .par 格式和自定义 CSV。
        返回 (nt, 6)。
        """
        if not os.path.exists(motion_file):
            return np.zeros((self.nt, 6))
        try:
            mp = np.loadtxt(motion_file)
            if mp.ndim == 1:
                mp = mp.reshape(1, -1)
            if mp.shape[0] != self.nt:
                # 可能行数不对 (mcflirt输出nt-1行)
                if mp.shape[0] == self.nt - 1:
                    mp = np.vstack([np.zeros((1, mp.shape[1])), mp])
            return mp[:, :6]
        except Exception:
            return np.zeros((self.nt, 6))

    def compute_fd_mm(self, motion_params: np.ndarray,
                      tr_mm: float = 50.0) -> np.ndarray:
        """
        计算 Framewise Displacement (mm)。
        旋转参数乘以转换半径 (默认 50 mm) 转为 mm 单位。
        Returns: (nt,)  第一帧为0
        """
        if motion_params is None or np.all(motion_params == 0):
            return np.zeros(self.nt)
        mp   = motion_params.copy()
        mp[:, 3:] *= tr_mm          # 旋转 rad → mm
        diff = np.diff(mp, axis=0)
        fd   = np.abs(diff).sum(axis=1)
        return np.concatenate([[0], fd])

    def build_24param_matrix(self, motion_params: np.ndarray) -> np.ndarray:
        """
        构造 24 参数运动协变量矩阵：
        6 params + 6 derivative + 6 squared + 6 derivative_squared
        Returns: (nt, 24)
        """
        mp     = motion_params                           # (nt, 6)
        deriv  = np.diff(mp, axis=0, prepend=mp[:1])    # (nt, 6)
        sq     = mp ** 2
        dsq    = deriv ** 2
        return np.hstack([mp, deriv, sq, dsq])          # (nt, 24)

    # ── WM / CSF 信号 ─────────────────────────────────────────────────────────
    def extract_wm_csf_signals(self, data_4d: np.ndarray,
                                tissue_seg: np.ndarray = None) -> dict:
        """
        提取白质和 CSF 的平均时间序列。
        tissue_seg: (nx,ny,nz) 1=CSF 2=GM 3=WM（T1分割结果）
        若无 T1 分割，使用极端强度阈值近似。
        Returns: {'WM': (nt,), 'CSF': (nt,)}
        """
        nx, ny, nz, nt = data_4d.shape
        signals = {}

        if tissue_seg is not None:
            wm_mask  = (tissue_seg == 3)
            csf_mask = (tissue_seg == 1)
        else:
            # 无分割时: 高强度近似WM, 极低值近似CSF
            mean_vol = data_4d.mean(axis=3)
            wm_th    = np.percentile(mean_vol[self.mask], 80)
            csf_th   = np.percentile(mean_vol[self.mask], 20)
            wm_mask  = (mean_vol > wm_th)  & self.mask
            csf_mask = (mean_vol < csf_th) & self.mask

        # 腐蚀确保安全边界
        wm_mask  = ndimage.binary_erosion(wm_mask,  iterations=1)
        csf_mask = ndimage.binary_erosion(csf_mask, iterations=1)

        signals['WM']  = data_4d[wm_mask].mean(axis=0)  if wm_mask.sum()  > 5 else np.zeros(nt)
        signals['CSF'] = data_4d[csf_mask].mean(axis=0) if csf_mask.sum() > 5 else np.zeros(nt)
        return signals

    # ── 主回归函数 ────────────────────────────────────────────────────────────
    def regress(self, motion_params: np.ndarray = None,
                 wm_csf_signals: dict = None,
                 include_gsr: bool = False,
                 n_motion_params: int = 6) -> np.ndarray:
        """
        从 ts_brain 中回归出噪声协变量。

        motion_params    : (nt, 6)  运动参数; None → 不回归
        wm_csf_signals   : dict 含 'WM', 'CSF'; None → 不回归
        include_gsr      : 是否回归全局信号 (默认 False)
        n_motion_params  : 6 或 24

        Returns: ts_clean (N_vox, nt)
        """
        nt = self.nt
        confounds = []

        # 截距 + 线性趋势（保留低频）
        confounds.append(np.ones(nt))
        confounds.append(np.arange(nt, dtype=float))

        # 运动参数
        if motion_params is not None and not np.all(motion_params == 0):
            if n_motion_params == 24:
                confounds.append(self.build_24param_matrix(motion_params))
            else:
                confounds.append(motion_params)

        # WM / CSF
        if wm_csf_signals:
            for sig in wm_csf_signals.values():
                if not np.all(sig == 0):
                    confounds.append(sig)
                    # 一阶导数
                    confounds.append(np.concatenate([[0], np.diff(sig)]))

        # 全局信号
        if include_gsr:
            gs = self.ts.mean(axis=0)
            confounds.append(gs)
            confounds.append(np.concatenate([[0], np.diff(gs)]))

        # 构造设计矩阵 X (nt × nconf)
        X_list = []
        for c in confounds:
            if c.ndim == 1:
                X_list.append(c.reshape(-1, 1))
            else:
                X_list.append(c)
        X = np.hstack(X_list)                      # (nt, nconf)

        # OLS: beta = (X'X)^-1 X' y^T
        beta, _, _, _ = np.linalg.lstsq(X, self.ts.T, rcond=None)  # (nconf, N_vox)
        ts_clean = self.ts - (X @ beta).T          # residual (N_vox, nt)

        np.save(os.path.join(self.out, "ts_nuisance_clean.npy"), ts_clean)
        return ts_clean


# ─────────────────────────────────────────────────────────────────────────────
# 2. CARPET PLOT & ADVANCED QC
# ─────────────────────────────────────────────────────────────────────────────

class CarpetPlotQC:
    """
    Carpet plot (grayplot) + FD分布 + Scrubbing 建议
    参考: Power et al. 2017, NeuroImage
    """

    def __init__(self, data_4d: np.ndarray, mask: np.ndarray,
                 fd: np.ndarray, dvars: np.ndarray,
                 TR: float, output_dir: str):
        self.data   = data_4d    # (nx,ny,nz,nt)
        self.mask   = mask
        self.fd     = fd         # (nt,)
        self.dvars  = dvars      # (nt,)
        self.TR     = TR
        self.out    = output_dir

    # ── Scrubbing 建议 ────────────────────────────────────────────────────────
    def recommend_scrubbing(self, fd_thresh: float = 0.5,
                             dvars_pct_thresh: float = 5.0) -> dict:
        """
        返回建议去除的时间点及其理由。
        fd_thresh       : FD阈值 (mm or proxy%)
        dvars_pct_thresh: DVARS%阈值
        """
        bad_fd    = np.where(self.fd    > fd_thresh)[0].tolist()
        bad_dvars = np.where(self.dvars > dvars_pct_thresh)[0].tolist()
        scrub_idx = sorted(set(bad_fd) | set(bad_dvars))

        # 剔除后仍有足够时间点?
        nt        = len(self.fd)
        n_remain  = nt - len(scrub_idx)
        usable    = n_remain >= 150

        result = {
            "n_total":        int(nt),
            "n_scrubbed":     len(scrub_idx),
            "n_remaining":    int(n_remain),
            "pct_scrubbed":   round(len(scrub_idx) / nt * 100, 1),
            "usable_after_scrubbing": bool(usable),
            "fd_threshold_used":    fd_thresh,
            "dvars_threshold_used": dvars_pct_thresh,
            "scrubbed_volumes": scrub_idx,
            "bad_fd_volumes":   bad_fd,
            "bad_dvars_volumes":bad_dvars,
        }
        np.save(os.path.join(self.out, "scrub_mask.npy"),
                np.array([i not in scrub_idx for i in range(nt)]))
        with open(os.path.join(self.out, "scrubbing_result.json"), "w") as f:
            json.dump(result, f, indent=2)
        return result

    # ── Carpet Plot ───────────────────────────────────────────────────────────
    def generate_carpet_plot(self, tissue_seg: np.ndarray = None,
                              n_voxels: int = 4000) -> str:
        """
        生成 carpet plot (grayplot)：
          - 纵轴: 按组织分层的体素
          - 横轴: 时间
          - 顶部: FD + DVARS 时间序列
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import Normalize

        nt = self.data.shape[3]
        t  = np.arange(nt) * self.TR

        # 按组织分层体素
        brain_vox = self.data[self.mask]   # (N_vox, nt)
        N_vox     = brain_vox.shape[0]

        if tissue_seg is not None:
            # 分层排序: WM → GM → CSF
            ts_mask_flat  = self.mask.ravel()
            seg_flat      = tissue_seg.ravel()
            brain_seg     = seg_flat[ts_mask_flat]     # segment label per brain voxel
            order = np.argsort(brain_seg)[::-1]        # WM(3) → GM(2) → CSF(1)
        else:
            order = np.arange(N_vox)

        # 随机子采样 (carpet plot 通常显示 ~4000 体素)
        if N_vox > n_voxels:
            rng   = np.random.default_rng(42)
            samp  = rng.choice(len(order), n_voxels, replace=False)
            samp  = np.sort(samp)
            order = order[samp]

        carpet = brain_vox[order]          # (n_voxels, nt)
        # z-score per voxel
        mu  = carpet.mean(axis=1, keepdims=True)
        sd  = carpet.std(axis=1,  keepdims=True) + 1e-8
        carpet_z = (carpet - mu) / sd

        # ── Figure ────────────────────────────────────────────────────────────
        fig = plt.figure(figsize=(14, 8))
        gs  = fig.add_gridspec(4, 1, height_ratios=[1, 1, 4, 0.1], hspace=0.08)

        # Row 0: FD
        ax0 = fig.add_subplot(gs[0])
        ax0.plot(t, self.fd, color="#E74C3C", lw=0.8)
        ax0.axhline(0.5, ls="--", color="gray", lw=0.7, label="FD=0.5")
        ax0.set_ylabel("FD proxy\n(% or mm)", fontsize=8)
        ax0.set_xlim(t[0], t[-1]); ax0.tick_params(labelbottom=False)
        ax0.legend(fontsize=7, loc="upper right")

        # Row 1: DVARS
        ax1 = fig.add_subplot(gs[1])
        ax1.plot(t, self.dvars, color="#3498DB", lw=0.8)
        ax1.axhline(5.0, ls="--", color="gray", lw=0.7, label="DVARS=5%")
        ax1.set_ylabel("DVARS (%)", fontsize=8)
        ax1.set_xlim(t[0], t[-1]); ax1.tick_params(labelbottom=False)
        ax1.legend(fontsize=7, loc="upper right")

        # Row 2: Carpet
        ax2 = fig.add_subplot(gs[2])
        im  = ax2.imshow(carpet_z, aspect="auto", interpolation="none",
                          cmap="gray", vmin=-2, vmax=2,
                          extent=[t[0], t[-1], carpet_z.shape[0], 0])
        ax2.set_xlabel("Time (s)", fontsize=9)
        ax2.set_ylabel(f"Voxels (N={len(order)})", fontsize=8)
        ax2.set_xlim(t[0], t[-1])

        # 颜色条
        ax3 = fig.add_subplot(gs[3])
        plt.colorbar(im, cax=ax3, orientation="horizontal", label="z-score")

        fig.suptitle("Carpet Plot (Grayplot) — Data Quality Visualization\n"
                     "Voxels sorted by tissue type; z-scored per voxel",
                     fontsize=10)
        out_path = os.path.join(self.out, "carpet_plot.png")
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return out_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. PURE-PYTHON MOTION ESTIMATION (phase correlation, 3D translations)
# ─────────────────────────────────────────────────────────────────────────────

class MotionEstimator:
    """
    纯 Python 3D 平移运动估计（相位相关法）。
    不依赖 FSL/ANTs。估计3轴平移；旋转设为0（简化）。
    生成运动参数文件，供 NuisanceRegressor 使用。
    """

    def __init__(self, data_4d: np.ndarray, TR: float,
                 output_dir: str, progress_cb=None):
        self.data = data_4d          # (nx,ny,nz,nt)
        self.TR   = TR
        self.out  = output_dir
        self.cb   = progress_cb or (lambda p, m: None)
        self.voxel_size = 3.5        # mm per voxel (placeholder)

    def estimate_translations(self) -> np.ndarray:
        """
        对每个时间点估计相对于参考帧（vol 0）的3D平移。
        返回 (nt, 6)，旋转列为0。
        """
        nt      = self.data.shape[3]
        ref_vol = self.data[..., 0].astype(np.float32)

        # 预计算参考的 FFT
        ref_fft = np.fft.fftn(ref_vol)
        ref_conj = np.conj(ref_fft)

        motion = np.zeros((nt, 6))
        self.cb(1, f"运动估计：相位相关法 ({nt} 帧)...")
        for t in range(1, nt):
            vol_fft = np.fft.fftn(self.data[..., t].astype(np.float32))
            cross   = ref_conj * vol_fft
            norm    = np.abs(cross) + 1e-10
            R       = np.fft.ifftn(cross / norm).real
            peak    = np.unravel_index(np.argmax(R), R.shape)
            # 处理 wrap-around
            shifts  = [p if p < s//2 else p - s
                       for p, s in zip(peak, R.shape)]
            # 转为 mm
            motion[t, :3] = [s * self.voxel_size for s in shifts]
            if t % 50 == 0:
                self.cb(1, f"  运动估计: {t}/{nt}...")

        # FD 计算（仅平移，旋转=0）
        fd = np.concatenate([[0], np.abs(np.diff(motion[:, :3], axis=0)).sum(axis=1)])

        # 保存
        motion_file = os.path.join(self.out, "motion_params_6dof.txt")
        np.savetxt(motion_file, motion, fmt="%.6f",
                   header="tx(mm) ty(mm) tz(mm) rx(rad) ry(rad) rz(rad)")
        fd_file = os.path.join(self.out, "fd_mm.npy")
        np.save(fd_file, fd)
        self.cb(1, f"运动估计完成: max FD={fd.max():.2f}mm  mean={fd.mean():.2f}mm")
        return motion


# ─────────────────────────────────────────────────────────────────────────────
# 4. SCHAEFER / AAL ROI SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

class AtlasROIExtractor:
    """
    基于 nilearn 的 Schaefer-2018 ROI 时间序列提取。
    支持: Schaefer 100 / 200 / 400 parcels, 7 Networks。
    回退: MNI 球形种子（当 atlas 下载失败时）。
    """

    SCHAEFER_NETWORKS_7 = [
        "Vis", "SomMot", "DorsAttn", "SalVentAttn",
        "Limbic", "Cont", "Default"
    ]
    SCHAEFER_CN = {
        "Vis":         "视觉网络",
        "SomMot":      "感觉运动网络",
        "DorsAttn":    "背侧注意网络",
        "SalVentAttn": "凸显/腹侧注意网络",
        "Limbic":      "边缘系统",
        "Cont":        "执行控制网络",
        "Default":     "默认模式网络",
    }

    def __init__(self, n_rois: int = 100, output_dir: str = "."):
        assert n_rois in (100, 200, 400), "Schaefer parcels 必须为100/200/400"
        self.n_rois = n_rois
        self.out    = output_dir
        self.atlas  = None
        self.labels = []

    def load_schaefer(self) -> bool:
        """下载/加载 Schaefer-2018 atlas。返回 True 表示成功。"""
        try:
            from nilearn import datasets
            sch = datasets.fetch_atlas_schaefer_2018(
                n_rois=self.n_rois, yeo_networks=7, resolution_mm=1)
            self.atlas  = sch["maps"]
            self.labels = list(sch["labels"])
            return True
        except Exception as e:
            print(f"  Schaefer atlas 加载失败 ({e})，回退到 MNI 球形ROI")
            return False

    def extract_timeseries(self, nifti_path: str,
                            smoothing_fwhm: float = 6.0) -> tuple:
        """
        从 NIfTI 4D 影像提取 ROI 时间序列。
        Returns: (ts_array (nt, n_rois), labels list, network_labels list)
        """
        if not self.load_schaefer():
            return None, [], []

        from nilearn.maskers import NiftiLabelsMasker
        masker = NiftiLabelsMasker(
            labels_img=self.atlas,
            standardize=True,
            smoothing_fwhm=smoothing_fwhm,
            memory_level=0,
            verbose=0,
        )
        ts = masker.fit_transform(nifti_path)    # (nt, n_rois)

        # NiftiLabelsMasker 跳过 label=0 (Background)，labels[0]="Background"
        # ts.shape[1] == n_rois == len(labels) - 1  → 跳过首个 Background 标签
        active_labels = self.labels[1:] if (
            len(self.labels) == ts.shape[1] + 1) else self.labels[:ts.shape[1]]

        net_labels = []
        for lbl in active_labels:
            if isinstance(lbl, bytes):
                lbl = lbl.decode()
            parts = lbl.split("_")
            net = next((p for p in parts if p in self.SCHAEFER_NETWORKS_7), "Other")
            net_labels.append(net)

        # 保存
        np.save(os.path.join(self.out, f"schaefer{self.n_rois}_timeseries.npy"), ts)
        with open(os.path.join(self.out, f"schaefer{self.n_rois}_labels.json"), "w") as f:
            json.dump({"labels": [str(l) for l in self.labels],
                       "networks": net_labels}, f, indent=2)
        return ts, self.labels, net_labels

    def compute_fc_matrix(self, ts: np.ndarray) -> np.ndarray:
        """Pearson r FC matrix, Fisher-Z transformed."""
        FC   = np.corrcoef(ts.T)
        FC_z = np.arctanh(np.clip(FC, -0.9999, 0.9999))
        np.fill_diagonal(FC,   0)
        np.fill_diagonal(FC_z, 0)
        np.save(os.path.join(self.out, f"schaefer{self.n_rois}_FC_pearson.npy"),  FC)
        np.save(os.path.join(self.out, f"schaefer{self.n_rois}_FC_fisherZ.npy"), FC_z)
        return FC

    def network_stats(self, FC: np.ndarray, net_labels: list) -> dict:
        """计算每个网络的内部 FC 均值。"""
        nets   = sorted(set(net_labels))
        stats  = {}
        idx    = np.array(net_labels)
        for net in nets:
            mask = (idx == net)
            if mask.sum() < 2:
                continue
            sub   = FC[np.ix_(mask, mask)]
            upper = sub[np.triu_indices(mask.sum(), k=1)]
            stats[net] = {
                "n_rois":  int(mask.sum()),
                "mean_FC": round(float(upper.mean()), 4),
                "std_FC":  round(float(upper.std()),  4),
                "cn":      self.SCHAEFER_CN.get(net, net),
            }
        with open(os.path.join(self.out, f"schaefer{self.n_rois}_network_stats.json"), "w") as f:
            json.dump(stats, f, indent=2)
        return stats


# ─────────────────────────────────────────────────────────────────────────────
# 5. PIPELINE CONFIG & REPRODUCIBILITY
# ─────────────────────────────────────────────────────────────────────────────

class PipelineConfig:
    """
    记录并保存完整管线配置，生成可重复性摘要。
    """
    VERSION = "2.1.0"

    DEFAULT_CONFIG = {
        "version":  "2.1.0",
        "preprocessing": {
            "n_discard_trs":   5,
            "slice_timing":    "linear_interpolation",
            "motion_correction": "phase_correlation_3dof",
            "bandpass_hz":     [0.01, 0.10],
            "bandpass_order":  4,
            "bandpass_type":   "butterworth_filtfilt",
            "smoothing_fwhm_mm": 6.0,
            "normalization":   "PSC",
        },
        "nuisance_regression": {
            "enabled":         True,
            "motion_params":   6,       # 6 or 24
            "wm_regression":   True,
            "csf_regression":  True,
            "gsr":             False,
        },
        "quality_control": {
            "fd_threshold_mm":   0.5,
            "dvars_pct_thresh":  5.0,
            "scrubbing":         True,
            "min_trs_after_scrub": 150,
        },
        "roi_system": {
            "atlas":    "schaefer_2018",
            "n_parcels": 100,
            "fallback": "mni_33roi",
        },
        "functional_connectivity": {
            "kind":      "pearson_r",
            "fisher_z":  True,
        },
        "alff": {
            "freq_band": [0.01, 0.10],
        },
        "reho": {
            "neighborhood": "3x3x3",
            "method":       "kendall_w",
        },
        "graph_theory": {
            "threshold_r":  0.20,
            "hub_top_pct":  75,
        },
        "dynamic_fc": {
            "window_trs":    44,
            "step_trs":       4,
            "n_states_kmeans": 2,
            "random_seed":   42,
        },
    }

    def __init__(self, output_dir: str, overrides: dict = None):
        self.out = output_dir
        self.cfg = dict(self.DEFAULT_CONFIG)
        if overrides:
            self._deep_update(self.cfg, overrides)

    @staticmethod
    def _deep_update(d: dict, u: dict):
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                PipelineConfig._deep_update(d[k], v)
            else:
                d[k] = v

    def save_yaml(self) -> str:
        """保存为 YAML 格式（如果 PyYAML 可用则用 YAML，否则 JSON）。"""
        try:
            import yaml
            out_path = os.path.join(self.out, "pipeline_config.yaml")
            with open(out_path, "w") as f:
                yaml.dump(self.cfg, f, default_flow_style=False, allow_unicode=True)
        except ImportError:
            out_path = os.path.join(self.out, "pipeline_config.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)
        return out_path

    def compute_reproducibility_hash(self,
                                      nifti_path: str = None,
                                      results_dir: str = None) -> dict:
        """
        计算可重复性哈希：
          - config_hash : SHA-256 of pipeline config
          - data_hash   : SHA-256 of BOLD nifti (if provided)
          - results_hash: SHA-256 of key result files
        """
        hashes = {}

        # Config hash
        cfg_str = json.dumps(self.cfg, sort_keys=True)
        hashes["config_hash"]    = hashlib.sha256(cfg_str.encode()).hexdigest()
        hashes["config_version"] = self.VERSION

        # Data hash (large file — only hash first 1MB for speed)
        if nifti_path and os.path.exists(nifti_path):
            h = hashlib.sha256()
            with open(nifti_path, "rb") as f:
                h.update(f.read(1024 * 1024))   # 1 MB
            hashes["bold_nifti_partial_sha256"] = h.hexdigest()
            hashes["bold_nifti_size_bytes"]     = os.path.getsize(nifti_path)

        # Results hash
        if results_dir and os.path.isdir(results_dir):
            key_files = ["FC_pearson.npy", "qc_metrics.json",
                         "graph_metrics.json", "dFC_results.json"]
            res_hash  = hashlib.sha256()
            for fn in sorted(key_files):
                fp = os.path.join(results_dir, fn)
                if os.path.exists(fp):
                    with open(fp, "rb") as f:
                        res_hash.update(f.read())
            hashes["results_hash"] = res_hash.hexdigest()

        hashes["timestamp"] = __import__("datetime").datetime.now().isoformat()
        out_path = os.path.join(self.out, "reproducibility.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(hashes, f, indent=2)
        return hashes

    def snapshot(self, additional_info: dict = None) -> str:
        """保存版本化管线快照（config + 版本信息 + 软件列表）."""
        snap = {
            "pipeline_version": self.VERSION,
            "config":           self.cfg,
            "software": {
                "python":     __import__("sys").version.split()[0],
                "nibabel":    __import__("nibabel").__version__,
                "nilearn":    __import__("nilearn").__version__,
                "numpy":      __import__("numpy").__version__,
                "scipy":      __import__("scipy").__version__,
                "sklearn":    __import__("sklearn").__version__,
            },
        }
        if additional_info:
            snap["metadata"] = additional_info
        out_path = os.path.join(self.out,
            f"pipeline_snapshot_v{self.VERSION}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
        return out_path
