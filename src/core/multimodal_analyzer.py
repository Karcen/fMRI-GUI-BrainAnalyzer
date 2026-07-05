#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态神经影像分析模块 v1.0
支持: T1结构像 / DTI弥散 / QSM / MRA (TOF)
不依赖 dipy / FSL / AFNI — 纯 Python 实现
"""
import os, json, shutil, subprocess, glob, warnings
import numpy as np
import nibabel as nib
from scipy import ndimage
from scipy.ndimage import gaussian_filter
from sklearn.mixture import GaussianMixture
warnings.filterwarnings('ignore')


# ─── 主要WM束的参考FA值（正常成人，文献均值±SD）────────────────────────────
WM_REFERENCE_FA = {
    "Corpus Callosum":            {"mean": 0.72, "sd": 0.06, "desc": "胼胝体"},
    "Corticospinal Tract (L)":    {"mean": 0.60, "sd": 0.07, "desc": "皮质脊髓束（左）"},
    "Corticospinal Tract (R)":    {"mean": 0.60, "sd": 0.07, "desc": "皮质脊髓束（右）"},
    "Uncinate Fasciculus (L)":    {"mean": 0.44, "sd": 0.05, "desc": "钩束（左）"},
    "Uncinate Fasciculus (R)":    {"mean": 0.44, "sd": 0.05, "desc": "钩束（右）"},
    "Cingulum (L)":               {"mean": 0.48, "sd": 0.06, "desc": "扣带束（左）"},
    "Cingulum (R)":               {"mean": 0.48, "sd": 0.06, "desc": "扣带束（右）"},
    "Inferior Fronto-Occipital (L)":{"mean": 0.52, "sd": 0.05, "desc": "下额枕束（左）"},
    "Superior Longitudinal (L)":  {"mean": 0.46, "sd": 0.05, "desc": "上纵束（左）"},
    "Superior Longitudinal (R)":  {"mean": 0.46, "sd": 0.05, "desc": "上纵束（右）"},
}


class MultimodalAnalyzer:
    """T1 / DTI / QSM / MRA 多模态分析引擎"""

    def __init__(self, dicom_root: str, output_dir: str,
                 progress_cb=None):
        self.dicom_root  = dicom_root
        self.output_dir  = output_dir
        self.progress_cb = progress_cb or (lambda p, m: print(f"[{p:3d}%] {m}"))

        self.mm_dir      = os.path.join(output_dir, "multimodal")
        self.nifti_dir   = os.path.join(output_dir, "nifti")
        self.results_dir = os.path.join(output_dir, "results")
        self.plots_dir   = os.path.join(output_dir, "plots")
        self.imgs_dir    = os.path.join(output_dir, "report_imgs")
        for d in [self.mm_dir, self.nifti_dir, self.results_dir,
                  self.plots_dir, self.imgs_dir]:
            os.makedirs(d, exist_ok=True)

    # ─── dcm2niix helper ──────────────────────────────────────────────────────

    def _dcm2niix(self, dicom_folder: str, prefix: str) -> dict:
        """Run dcm2niix and return dict of {type: path}"""
        for p in ["/opt/homebrew/bin/dcm2niix", "/usr/local/bin/dcm2niix",
                  shutil.which("dcm2niix") or ""]:
            if p and os.path.isfile(p):
                dcm2niix = p; break
        else:
            raise RuntimeError("找不到 dcm2niix")
        cmd = [dcm2niix, "-z", "y", "-b", "y", "-f", prefix,
               "-o", self.nifti_dir, dicom_folder]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"dcm2niix failed: {result.stderr[:300]}")
        out = {}
        out["nii"] = glob.glob(os.path.join(self.nifti_dir, f"{prefix}*.nii.gz"))
        out["json"]= glob.glob(os.path.join(self.nifti_dir, f"{prefix}*.json"))
        out["bvec"]= glob.glob(os.path.join(self.nifti_dir, f"{prefix}*.bvec"))
        out["bval"]= glob.glob(os.path.join(self.nifti_dir, f"{prefix}*.bval"))
        return out

    # ─────────────────────────────────────────────────────────────────────────
    # T1 STRUCTURAL ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    def analyze_t1(self, t1_folder: str) -> dict:
        """
        T1 结构像分析：
          1. DICOM → NIfTI (dcm2niix)
          2. 脑掩码（强度阈值 + 形态学）
          3. 3类 GMM 组织分割 (WM / GM / CSF)
          4. 体积估算
          5. 对称性评估（半球体积比较）
        """
        self.progress_cb(2, "T1 结构像：DICOM 转换...")
        files = self._dcm2niix(t1_folder, "t1")
        nii_files = [f for f in files["nii"] if "t1" in os.path.basename(f)]
        if not nii_files:
            raise RuntimeError("T1 NIfTI 转换失败")
        t1_path = nii_files[0]

        self.progress_cb(5, "T1：脑掩码 + 组织分割...")
        img  = nib.load(t1_path)
        data = img.get_fdata(dtype=np.float32).squeeze()  # 3D
        zooms = img.header.get_zooms()[:3]
        vox_vol_cc = float(np.prod(zooms)) / 1000.0  # cc per voxel

        # 脑掩码：阈值 + 最大连通域（排除头皮/颈部脂肪）
        thresh   = data.max() * 0.20          # 20% of max → ~1000cc for typical T1
        mask     = data > thresh
        # 保留最大连通域（脑实质）
        labeled, n_comp = ndimage.label(mask)
        if n_comp > 0:
            comp_sizes = ndimage.sum(mask, labeled, range(1, n_comp+1))
            largest    = int(np.argmax(comp_sizes)) + 1
            mask       = (labeled == largest)
        mask     = ndimage.binary_fill_holes(mask)
        mask     = ndimage.binary_closing(mask, iterations=4)
        mask     = ndimage.binary_erosion(mask, iterations=1)
        mask     = ndimage.binary_dilation(mask, iterations=1)

        brain_vol_cc = float(mask.sum()) * vox_vol_cc

        # 3类 GMM 组织分割（脑内体素）
        brain_vox  = data[mask].reshape(-1, 1)
        gmm        = GaussianMixture(n_components=3, random_state=42,
                                      covariance_type='full', n_init=3)
        labels_1d  = gmm.fit_predict(brain_vox)
        means      = gmm.means_.flatten()
        order      = np.argsort(means)  # CSF < GM < WM
        remap      = {order[0]: 0, order[1]: 1, order[2]: 2}  # 0=CSF,1=GM,2=WM
        labels_1d  = np.array([remap[l] for l in labels_1d])

        tissue_map = np.zeros(data.shape, dtype=np.uint8)
        tissue_map[mask] = labels_1d + 1  # 1=CSF, 2=GM, 3=WM

        csf_vol = float((labels_1d == 0).sum()) * vox_vol_cc
        gm_vol  = float((labels_1d == 1).sum()) * vox_vol_cc
        wm_vol  = float((labels_1d == 2).sum()) * vox_vol_cc

        # 对称性
        nx = data.shape[0]
        L_mask = mask.copy(); L_mask[nx//2:] = False
        R_mask = mask.copy(); R_mask[:nx//2] = False
        L_vol  = float(L_mask.sum()) * vox_vol_cc
        R_vol  = float(R_mask.sum()) * vox_vol_cc
        symmetry = float(min(L_vol, R_vol) / max(L_vol, R_vol)) if max(L_vol, R_vol)>0 else 1.0

        # 皮质厚度代理（GM 区域表面/体积比近似）
        gm_mask = (tissue_map == 2)
        gm_surface_vox = ndimage.binary_erosion(gm_mask).sum()
        ct_proxy = float(gm_vol / (gm_surface_vox * vox_vol_cc + 1e-6) * 3.0) if gm_surface_vox>0 else 2.5

        # 保存组织分割
        nib.save(nib.Nifti1Image(tissue_map.astype(np.uint8), img.affine),
                 os.path.join(self.mm_dir, "t1_tissue_seg.nii.gz"))

        results = {
            "t1_nifti":         t1_path,
            "brain_vol_cc":     round(brain_vol_cc, 1),
            "csf_vol_cc":       round(csf_vol, 1),
            "gm_vol_cc":        round(gm_vol, 1),
            "wm_vol_cc":        round(wm_vol, 1),
            "gm_wm_ratio":      round(gm_vol / max(wm_vol, 1), 3),
            "symmetry_index":   round(symmetry, 3),
            "ct_proxy_mm":      round(ct_proxy, 2),
            "voxel_vol_cc":     round(vox_vol_cc, 6),
            "matrix":           list(data.shape),
            "resolution_mm":    [round(float(z), 3) for z in zooms],
        }

        # 参考值比较（成人男性25岁）
        ref = {"brain_vol_cc": 1400, "gm_vol_cc": 700, "wm_vol_cc": 500,
               "csf_vol_cc": 150, "gm_wm_ratio": 1.40}
        interpretation = []
        if abs(brain_vol_cc - ref["brain_vol_cc"]) > 200:
            interpretation.append(f"脑总体积偏{'大' if brain_vol_cc>ref['brain_vol_cc'] else '小'}")
        if symmetry < 0.90:
            interpretation.append("半球不对称性较明显")
        elif symmetry >= 0.95:
            interpretation.append("半球对称性良好")
        if gm_vol < ref["gm_vol_cc"] * 0.85:
            interpretation.append("灰质体积偏低（注意：强度阈值分割，精度有限）")
        results["interpretation"] = interpretation if interpretation else ["脑结构参数在正常范围内"]

        with open(os.path.join(self.results_dir, "t1_results.json"),
                  "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        self.progress_cb(8, f"T1 完成: 脑={brain_vol_cc:.0f}cc  GM={gm_vol:.0f}cc  WM={wm_vol:.0f}cc  对称性={symmetry:.3f}")
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # DTI ANALYSIS (pure numpy / scipy — no dipy)
    # ─────────────────────────────────────────────────────────────────────────

    def analyze_dti(self, dti_folder: str) -> dict:
        """
        DTI 弥散张量分析（纯 numpy OLS 实现）：
          1. DICOM → NIfTI + bvec/bval
          2. 脑掩码
          3. OLS 张量拟合
          4. FA / MD / AD / RD 图谱
          5. ROI-based 主要 WM 束分析（基于 MNI 种子坐标，原生空间近似）
        """
        self.progress_cb(10, "DTI：DICOM 转换...")
        files = self._dcm2niix(dti_folder, "dti")
        nii_f  = [f for f in files["nii"] if "dti" in os.path.basename(f)]
        bvec_f = files.get("bvec", [])
        bval_f = files.get("bval", [])

        if not nii_f or not bvec_f or not bval_f:
            raise RuntimeError("DTI NIfTI / bvec / bval 转换失败")

        dti_path = nii_f[0]
        bvec     = np.loadtxt(bvec_f[0])  # (3, N)
        bval     = np.loadtxt(bval_f[0])  # (N,)

        self.progress_cb(13, f"DTI 加载: {nib.load(dti_path).shape}  b-shells={sorted(set(bval.astype(int).tolist()))}")
        img  = nib.load(dti_path)
        data = img.get_fdata(dtype=np.float32)
        nx, ny, nz, nd = data.shape
        zooms = img.header.get_zooms()[:3]

        # 选择 b0 和 DWI 体积
        b0_idx  = np.where(bval < 50)[0]
        dwi_idx = np.where(bval >= 50)[0]

        if len(b0_idx) == 0 or len(dwi_idx) < 6:
            raise RuntimeError(f"DTI 数据不足：b0={len(b0_idx)}  DWI={len(dwi_idx)}")

        S0   = data[..., b0_idx].mean(axis=-1)  # 平均 b0
        S0   = np.maximum(S0, 1e-6)

        self.progress_cb(16, "DTI：脑掩码...")
        thresh   = np.percentile(S0[S0 > S0.max()*0.05], 15)
        mask     = S0 > thresh
        mask     = ndimage.binary_fill_holes(mask)
        mask     = ndimage.binary_closing(mask, iterations=2)
        n_vox    = int(mask.sum())
        self.progress_cb(18, f"DTI 脑掩码: {n_vox} 体素")

        # ── OLS 张量拟合 ───────────────────────────────────────────────────────
        # Design matrix B (N_dwi × 6):  [bx², by², bz², 2bxby, 2bxbz, 2bybz]
        self.progress_cb(20, "DTI：OLS 张量拟合...")
        g  = bvec[:, dwi_idx].T        # (N_dwi, 3)
        b  = bval[dwi_idx]             # (N_dwi,)
        # build B matrix
        B  = np.column_stack([
            b * g[:,0]**2,
            b * g[:,1]**2,
            b * g[:,2]**2,
            2 * b * g[:,0] * g[:,1],
            2 * b * g[:,0] * g[:,2],
            2 * b * g[:,1] * g[:,2],
        ])   # (N_dwi, 6)
        BtB_inv_Bt = np.linalg.lstsq(B, np.eye(len(dwi_idx)), rcond=None)[0]  # (6, N_dwi) pseudo-inv

        # Extract brain voxels
        S_dwi  = data[..., dwi_idx][mask]  # (N_vox, N_dwi)
        S0_vox = S0[mask]                  # (N_vox,)

        # Log ratio (clipped for stability)
        ratio  = np.maximum(S_dwi, 1e-6) / S0_vox[:, None]
        log_S  = -np.log(np.clip(ratio, 1e-8, 1.0))  # (N_vox, N_dwi)

        # Solve: D_vec = B^+ log_S^T  →  log_S @ B^+ ^T
        D_vec  = log_S @ BtB_inv_Bt.T    # (N_vox, 6) [Dxx,Dyy,Dzz,Dxy,Dxz,Dyz]

        self.progress_cb(25, "DTI：特征值分解 → FA/MD/AD/RD...")
        # Reconstruct symmetric tensor and get eigenvalues
        Dxx, Dyy, Dzz = D_vec[:,0], D_vec[:,1], D_vec[:,2]
        Dxy, Dxz, Dyz = D_vec[:,3], D_vec[:,4], D_vec[:,5]

        # Batch eigenvalue decomposition (use closed-form for 3×3 symmetric)
        # Build tensor array (N_vox, 3, 3)
        Dtensor = np.zeros((n_vox, 3, 3), dtype=np.float32)
        Dtensor[:,0,0] = Dxx; Dtensor[:,1,1] = Dyy; Dtensor[:,2,2] = Dzz
        Dtensor[:,0,1] = Dtensor[:,1,0] = Dxy
        Dtensor[:,0,2] = Dtensor[:,2,0] = Dxz
        Dtensor[:,1,2] = Dtensor[:,2,1] = Dyz

        # Compute eigenvalues in batches
        BATCH = 5000
        evals  = np.zeros((n_vox, 3), dtype=np.float32)
        for i in range(0, n_vox, BATCH):
            ev = np.linalg.eigvalsh(Dtensor[i:i+BATCH])
            ev = np.sort(ev, axis=-1)[:, ::-1]   # descending
            evals[i:i+BATCH] = ev

        lam1, lam2, lam3 = evals[:,0], evals[:,1], evals[:,2]
        lam1 = np.maximum(lam1, 1e-10)
        lam2 = np.maximum(lam2, 1e-10)
        lam3 = np.maximum(lam3, 1e-10)

        MD  = (lam1 + lam2 + lam3) / 3.0
        AD  = lam1
        RD  = (lam2 + lam3) / 2.0
        num = np.sqrt((lam1-MD)**2 + (lam2-MD)**2 + (lam3-MD)**2)
        den = np.sqrt(lam1**2 + lam2**2 + lam3**2) + 1e-10
        FA  = np.sqrt(1.5) * num / den
        FA  = np.clip(FA, 0, 1)

        # 填回3D图谱
        def to_map(arr_1d):
            m = np.zeros(data.shape[:3], dtype=np.float32)
            m[mask] = arr_1d
            return m

        FA_map  = to_map(FA);  MD_map  = to_map(MD * 1e3)   # ×1000 for mm²/s
        AD_map  = to_map(AD * 1e3); RD_map  = to_map(RD * 1e3)

        # 保存 NIfTI
        aff = img.affine
        for arr, name in [(FA_map,"dti_FA"),(MD_map,"dti_MD"),(AD_map,"dti_AD"),(RD_map,"dti_RD")]:
            nib.save(nib.Nifti1Image(arr, aff),
                     os.path.join(self.mm_dir, f"{name}.nii.gz"))
        np.save(os.path.join(self.results_dir, "dti_FA_map.npy"),  FA_map)
        np.save(os.path.join(self.results_dir, "dti_MD_map.npy"),  MD_map)

        self.progress_cb(30, f"DTI 图谱: FA_mean={FA.mean():.3f}  MD_mean={MD.mean()*1e3:.3f}×10⁻³mm²/s")
        return FA_map, MD_map, AD_map, RD_map, mask, img

    def _dti_roi_stats(self, FA_map, MD_map, AD_map, RD_map, dti_img) -> dict:
        """
        基于 MNI 球形种子坐标（近似映射到原生空间）计算主要 WM 束 FA/MD。
        无需配准，适合单受试者探索性分析。
        """
        # 主要 WM 束 MNI 坐标（参考 JHU WM 图谱）
        WM_SEEDS = {
            "Corpus_Callosum_Genu":    (0, 28, 4),
            "Corpus_Callosum_Body":    (0, -4, 28),
            "Corpus_Callosum_Splenium":(0, -46, 20),
            "Cingulum_L":              (-6, -40, 28),
            "Cingulum_R":              (6,  -40, 28),
            "CST_L":                   (-20, -24, 56),
            "CST_R":                   (20,  -24, 56),
            "SLF_L":                   (-38, -20, 42),
            "SLF_R":                   (38,  -20, 42),
            "UF_L":                    (-28, 22,  -14),
            "UF_R":                    (28,  22,  -14),
            "IFOF_L":                  (-30, -8,  -20),
            "IFOF_R":                  (30,  -8,  -20),
        }
        aff_inv = np.linalg.inv(dti_img.affine)
        nx, ny, nz = FA_map.shape
        roi_stats: dict = {}

        for name, mni in WM_SEEDS.items():
            c = np.array([*mni, 1.0])
            v = aff_inv @ c
            cx, cy, cz = [int(round(float(x))) for x in v[:3]]
            r = 2  # 2-voxel sphere ≈ 4mm
            x0,x1 = max(0,cx-r), min(nx,cx+r+1)
            y0,y1 = max(0,cy-r), min(ny,cy+r+1)
            z0,z1 = max(0,cz-r), min(nz,cz+r+1)
            fa_patch = FA_map[x0:x1, y0:y1, z0:z1]
            md_patch = MD_map[x0:x1, y0:y1, z0:z1]
            ad_patch = AD_map[x0:x1, y0:y1, z0:z1]
            rd_patch = RD_map[x0:x1, y0:y1, z0:z1]
            valid    = fa_patch > 0.1  # exclude non-WM voxels
            if valid.sum() < 4:
                continue
            roi_stats[name] = {
                "FA_mean":  round(float(fa_patch[valid].mean()), 3),
                "FA_std":   round(float(fa_patch[valid].std()),  3),
                "MD_mean":  round(float(md_patch[valid].mean()), 3),
                "AD_mean":  round(float(ad_patch[valid].mean()), 3),
                "RD_mean":  round(float(rd_patch[valid].mean()), 3),
                "n_vox":    int(valid.sum()),
            }

        with open(os.path.join(self.results_dir, "dti_roi_stats.json"),
                  "w", encoding="utf-8") as f:
            json.dump(roi_stats, f, indent=2, ensure_ascii=False)
        return roi_stats

    def _dti_global_stats(self, FA_map, MD_map, AD_map, RD_map) -> dict:
        """全脑 WM 体素 (FA>0.2) 的全局 DTI 统计"""
        wm_mask = FA_map > 0.20
        if wm_mask.sum() < 100:
            return {}
        stats = {
            "WM_voxels":      int(wm_mask.sum()),
            "FA_mean":        round(float(FA_map[wm_mask].mean()), 3),
            "FA_std":         round(float(FA_map[wm_mask].std()),  3),
            "FA_median":      round(float(np.median(FA_map[wm_mask])), 3),
            "MD_mean_e3":     round(float(MD_map[wm_mask].mean()), 3),
            "AD_mean_e3":     round(float(AD_map[wm_mask].mean()), 3),
            "RD_mean_e3":     round(float(RD_map[wm_mask].mean()), 3),
            "AD_RD_ratio":    round(float(AD_map[wm_mask].mean() /
                                         max(RD_map[wm_mask].mean(), 1e-6)), 3),
        }
        # Normal reference (adult healthy WM)
        ref_fa = 0.45
        interpretation = []
        if stats["FA_mean"] < ref_fa * 0.85:
            interpretation.append("全脑 WM FA 偏低，提示白质完整性可能降低")
        elif stats["FA_mean"] > ref_fa * 1.15:
            interpretation.append("全脑 WM FA 偏高（需结合临床，注意伪影）")
        else:
            interpretation.append("全脑 WM FA 在正常参考范围内")
        if stats["RD_mean_e3"] > 0.65:
            interpretation.append("RD 偏高，提示可能存在髓鞘化异常（请结合临床）")
        stats["interpretation"] = interpretation
        return stats

    def analyze_dti_complete(self, dti_folder: str) -> dict:
        """DTI 完整分析入口：张量拟合 + 全局统计 + ROI 统计"""
        FA_map, MD_map, AD_map, RD_map, mask, dti_img = self.analyze_dti(dti_folder)
        self.progress_cb(32, "DTI：ROI 统计...")
        roi_stats    = self._dti_roi_stats(FA_map, MD_map, AD_map, RD_map, dti_img)
        global_stats = self._dti_global_stats(FA_map, MD_map, AD_map, RD_map)
        dti_results  = {
            "global": global_stats,
            "roi":    roi_stats,
            "n_directions": FA_map[mask].shape[0],
        }
        with open(os.path.join(self.results_dir, "dti_results.json"),
                  "w", encoding="utf-8") as f:
            json.dump(dti_results, f, indent=2, ensure_ascii=False)
        self.progress_cb(35, f"DTI 完成: FA={global_stats.get('FA_mean','?')}  ROI束={len(roi_stats)}")
        return dti_results

    # ─────────────────────────────────────────────────────────────────────────
    # QSM ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    def analyze_qsm(self, qsm_folder: str) -> dict:
        """
        QSM 铁沉积分析：
          1. dcm2niix → NIfTI
          2. 深部灰质 ROI（基底节、海马等）QSM 值提取
          3. 异常铁沉积评估
        """
        self.progress_cb(36, "QSM：DICOM 转换...")
        files = self._dcm2niix(qsm_folder, "qsm")
        nii_f = [f for f in files["nii"] if "qsm" in os.path.basename(f)]
        if not nii_f:
            return {"error": "QSM NIfTI 转换失败"}
        qsm_path = nii_f[0]

        img  = nib.load(qsm_path)
        data = img.get_fdata(dtype=np.float32).squeeze()
        aff_inv = np.linalg.inv(img.affine)
        nx, ny, nz = data.shape
        zooms = img.header.get_zooms()[:3]

        # 深部灰质 ROI MNI 坐标 (参考 Aquino et al. QSM 研究)
        DGM_ROIS = {
            "Caudate_L":      (-12, 16,  8),
            "Caudate_R":      (12,  16,  8),
            "Putamen_L":      (-26, 4,   0),
            "Putamen_R":      (26,  4,   0),
            "Globus_Pallidus_L": (-20, 0, -2),
            "Globus_Pallidus_R": (20,  0, -2),
            "Thalamus_L":     (-12, -20, 8),
            "Thalamus_R":     (12,  -20, 8),
            "Substantia_Nigra_L": (-8, -18, -10),
            "Substantia_Nigra_R": (8,  -18, -10),
            "Red_Nucleus_L":  (-5, -22, -8),
            "Red_Nucleus_R":  (5,  -22, -8),
            "Dentate_L":      (-14, -54, -28),
            "Dentate_R":      (14,  -54, -28),
        }

        def mni_to_vox(mni):
            c = np.array([*mni, 1.0])
            v = aff_inv @ c
            return [int(round(float(x))) for x in v[:3]]

        roi_qsm: dict = {}
        for name, mni in DGM_ROIS.items():
            cx, cy, cz = mni_to_vox(mni)
            r = 3  # 3-voxel sphere ≈ 3mm
            x0,x1 = max(0,cx-r), min(nx,cx+r+1)
            y0,y1 = max(0,cy-r), min(ny,cy+r+1)
            z0,z1 = max(0,cz-r), min(nz,cz+r+1)
            patch = data[x0:x1, y0:y1, z0:z1]
            if patch.size < 4:
                continue
            roi_qsm[name] = {
                "QSM_mean_ppb": round(float(patch.mean()), 2),
                "QSM_std_ppb":  round(float(patch.std()),  2),
                "n_vox":        int(patch.size),
            }

        # 参考值（健康成人 QSM ppb，文献均值）
        QSM_REF = {
            "Caudate":          {"mean": 30, "sd": 15},
            "Putamen":          {"mean": 60, "sd": 20},
            "Globus_Pallidus":  {"mean": 120,"sd": 30},
            "Thalamus":         {"mean": 20, "sd": 10},
            "Substantia_Nigra": {"mean": 80, "sd": 25},
            "Red_Nucleus":      {"mean": 60, "sd": 20},
            "Dentate":          {"mean": 40, "sd": 15},
        }
        interpretation = []
        for roi_name, vals in roi_qsm.items():
            ref_key = next((k for k in QSM_REF if k.lower() in roi_name.lower()), None)
            if ref_key:
                ref_m = QSM_REF[ref_key]["mean"]
                ref_s = QSM_REF[ref_key]["sd"]
                qval  = vals["QSM_mean_ppb"]
                if qval > ref_m + 2*ref_s:
                    interpretation.append(f"{roi_name}: QSM={qval:.1f}ppb，偏高（参考{ref_m}±{ref_s}ppb），提示铁含量增加")
        if not interpretation:
            interpretation.append("深部灰质 QSM 值在正常参考范围内，未见明显铁沉积异常")

        np.save(os.path.join(self.results_dir, "qsm_data.npy"), data)
        qsm_results = {
            "roi_stats": roi_qsm,
            "interpretation": interpretation,
            "qsm_nifti": qsm_path,
            "matrix": list(data.shape),
            "resolution_mm": [round(float(z),3) for z in zooms],
        }
        with open(os.path.join(self.results_dir, "qsm_results.json"),
                  "w", encoding="utf-8") as f:
            json.dump(qsm_results, f, indent=2, ensure_ascii=False)
        self.progress_cb(38, f"QSM 完成: {len(roi_qsm)} ROI，{len([i for i in interpretation if '偏高' in i])} 个异常")
        return qsm_results

    # ─────────────────────────────────────────────────────────────────────────
    # VISUALIZATIONS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_multimodal_images(self, t1_results, dti_results, qsm_results) -> list:
        """生成多模态报告图像"""
        self.progress_cb(40, "多模态可视化...")
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        files = []

        def savefig(name):
            p = os.path.join(self.imgs_dir, name)
            plt.savefig(p, dpi=150, bbox_inches="tight"); plt.close()
            files.append(p)

        # 1. T1 组织分割
        try:
            seg_path = os.path.join(self.mm_dir, "t1_tissue_seg.nii.gz")
            if os.path.exists(seg_path):
                seg = nib.load(seg_path).get_fdata()
                nz  = seg.shape[2]
                fig, axes = plt.subplots(1, 4, figsize=(14, 3))
                for col, sl in enumerate([nz//5, nz//3, nz//2, 2*nz//3]):
                    axes[col].imshow(seg[:,:,sl].T, cmap="Set1", origin="lower",
                                     vmin=0, vmax=3)
                    axes[col].set_title(f"Z={sl}"); axes[col].axis("off")
                fig.suptitle("T1 Tissue Segmentation (1=CSF, 2=GM, 3=WM)")
                plt.tight_layout(); savefig("t1_tissue_seg.png")
        except Exception as e: print(f"T1分割图警告: {e}")

        # 2. T1 体积饼图
        try:
            csf = t1_results.get("csf_vol_cc", 0)
            gm  = t1_results.get("gm_vol_cc",  0)
            wm  = t1_results.get("wm_vol_cc",  0)
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            axes[0].pie([csf, gm, wm], labels=["CSF","GM","WM"],
                        colors=["#3498DB","#2ECC71","#E74C3C"],
                        autopct="%1.1f%%", startangle=90)
            axes[0].set_title("Brain Tissue Composition")
            # bar chart with reference
            cats = ["CSF", "GM", "WM"]
            vals = [csf, gm, wm]
            refs = [150, 700, 500]
            x = np.arange(3)
            axes[1].bar(x-0.2, vals, 0.4, label="Subject", color=["#3498DB","#2ECC71","#E74C3C"])
            axes[1].bar(x+0.2, refs, 0.4, label="Reference", color="lightgray", alpha=0.7)
            axes[1].set_xticks(x); axes[1].set_xticklabels(cats)
            axes[1].set_ylabel("Volume (cc)"); axes[1].set_title("vs. Reference (Healthy Adult)")
            axes[1].legend()
            plt.tight_layout(); savefig("t1_volumes.png")
        except Exception as e: print(f"T1体积图警告: {e}")

        # 3. DTI FA 图
        try:
            fa_path = os.path.join(self.results_dir, "dti_FA_map.npy")
            md_path = os.path.join(self.results_dir, "dti_MD_map.npy")
            if os.path.exists(fa_path):
                FA = np.load(fa_path); MD = np.load(md_path)
                nz = FA.shape[2]
                fig, axes = plt.subplots(2, 4, figsize=(14, 6))
                for col, sl in enumerate([nz//5, nz//3, nz//2, 2*nz//3]):
                    axes[0,col].imshow(FA[:,:,sl].T, cmap="hot", origin="lower",
                                       vmin=0, vmax=0.8)
                    axes[0,col].set_title(f"FA Z={sl}"); axes[0,col].axis("off")
                    axes[1,col].imshow(MD[:,:,sl].T, cmap="Blues", origin="lower",
                                       vmin=0, vmax=1.5)
                    axes[1,col].set_title(f"MD Z={sl}"); axes[1,col].axis("off")
                fig.suptitle("DTI: FA (top) and MD×10⁻³mm²/s (bottom)")
                plt.tight_layout(); savefig("dti_FA_MD.png")
        except Exception as e: print(f"DTI图警告: {e}")

        # 4. DTI ROI FA 条形图（比较受试者vs文献均值）
        try:
            roi_stats = dti_results.get("roi", {})
            if roi_stats:
                names = list(roi_stats.keys())[:10]
                fa_vals = [roi_stats[n]["FA_mean"] for n in names]
                # 文献参考
                ref_map = {
                    "Corpus_Callosum_Genu": 0.75, "Corpus_Callosum_Body": 0.70,
                    "Corpus_Callosum_Splenium": 0.72,
                    "Cingulum_L": 0.48, "Cingulum_R": 0.48,
                    "CST_L": 0.60, "CST_R": 0.60,
                    "SLF_L": 0.46, "SLF_R": 0.46,
                    "UF_L": 0.44, "UF_R": 0.44,
                    "IFOF_L": 0.52, "IFOF_R": 0.52,
                }
                ref_vals = [ref_map.get(n, 0.50) for n in names]
                x = np.arange(len(names))
                fig, ax = plt.subplots(figsize=(12, 4))
                bars = ax.bar(x-0.2, fa_vals, 0.4, label="Subject", color="#3498DB", alpha=0.85)
                ax.bar(x+0.2, ref_vals, 0.4, label="Reference", color="lightgray", alpha=0.7)
                ax.set_xticks(x); ax.set_xticklabels([n.replace("_"," ") for n in names],
                                                       rotation=45, ha="right", fontsize=8)
                ax.set_ylabel("FA"); ax.set_title("WM Tract FA vs. Reference Values")
                ax.legend(); ax.set_ylim(0, 0.9)
                plt.tight_layout(); savefig("dti_tract_FA.png")
        except Exception as e: print(f"DTI ROI图警告: {e}")

        # 5. QSM 铁沉积图
        try:
            qsm_data_path = os.path.join(self.results_dir, "qsm_data.npy")
            if os.path.exists(qsm_data_path):
                qsm = np.load(qsm_data_path)
                nz  = qsm.shape[2]
                fig, axes = plt.subplots(1, 4, figsize=(14, 3))
                vmax = np.percentile(qsm[qsm > 0], 99) if (qsm > 0).any() else 200
                for col, sl in enumerate([nz//5, nz//3, nz//2, 2*nz//3]):
                    im = axes[col].imshow(qsm[:,:,sl].T, cmap="RdYlBu_r",
                                          origin="lower", vmin=-50, vmax=vmax)
                    axes[col].set_title(f"Z={sl}"); axes[col].axis("off")
                plt.colorbar(im, ax=axes[-1], label="QSM (ppb)")
                fig.suptitle("Quantitative Susceptibility Map (QSM) — Iron Mapping")
                plt.tight_layout(); savefig("qsm_iron_map.png")
        except Exception as e: print(f"QSM图警告: {e}")

        # 6. QSM ROI 条形图
        try:
            qsm_rois = qsm_results.get("roi_stats", {})
            QSM_REF  = {
                "Caudate": 30, "Putamen": 60, "Globus_Pallidus": 120,
                "Thalamus": 20, "Substantia_Nigra": 80,
                "Red_Nucleus": 60, "Dentate": 40,
            }
            if qsm_rois:
                names = list(qsm_rois.keys())
                vals  = [qsm_rois[n]["QSM_mean_ppb"] for n in names]
                refs  = [next((QSM_REF[k] for k in QSM_REF if k.lower() in n.lower()), 50) for n in names]
                x = np.arange(len(names))
                fig, ax = plt.subplots(figsize=(12, 4))
                colors_b = ["#E74C3C" if v > r*1.3 else "#2ECC71" for v, r in zip(vals, refs)]
                ax.bar(x-0.2, vals, 0.4, color=colors_b, alpha=0.85, label="Subject")
                ax.bar(x+0.2, refs, 0.4, color="lightgray", alpha=0.7, label="Reference")
                ax.set_xticks(x); ax.set_xticklabels([n.replace("_"," ") for n in names],
                                                       rotation=45, ha="right", fontsize=8)
                ax.set_ylabel("QSM (ppb)"); ax.set_title("Deep Gray Matter QSM vs. Reference")
                ax.legend()
                plt.tight_layout(); savefig("qsm_roi_bars.png")
        except Exception as e: print(f"QSM ROI图警告: {e}")

        self.progress_cb(43, f"多模态图像: {len(files)} 张")
        return files

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN PIPELINE
    # ─────────────────────────────────────────────────────────────────────────

    def run_all_multimodal(self, sequences: dict) -> dict:
        """
        自动运行所有可用模态的分析。
        sequences: {'t1': path, 'dti': path, 'qsm': path, ...}
        """
        results = {}
        if "t1" in sequences:
            try:
                results["t1"] = self.analyze_t1(sequences["t1"])
            except Exception as e:
                print(f"T1分析警告: {e}")
                results["t1"] = {"error": str(e)}
        if "dwi" in sequences:
            try:
                results["dti"] = self.analyze_dti_complete(sequences["dwi"])
            except Exception as e:
                print(f"DTI分析警告: {e}")
                results["dti"] = {"error": str(e)}
        if "qsm" in sequences:
            try:
                results["qsm"] = self.analyze_qsm(sequences["qsm"])
            except Exception as e:
                print(f"QSM分析警告: {e}")
                results["qsm"] = {"error": str(e)}
        # 生成图像
        t1_r  = results.get("t1",  {})
        dti_r = results.get("dti", {})
        qsm_r = results.get("qsm", {})
        try:
            results["images"] = self.generate_multimodal_images(t1_r, dti_r, qsm_r)
        except Exception as e:
            print(f"多模态图像警告: {e}")
            results["images"] = []
        with open(os.path.join(self.results_dir, "multimodal_results.json"),
                  "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in results.items() if k != "images"},
                      f, indent=2, ensure_ascii=False)
        self.progress_cb(45, f"多模态分析完成: {list(results.keys())}")
        return results
