"""Validate and load fMRIPrep volumetric derivatives without silent fallbacks."""
import csv
import json
import os
import re
from pathlib import Path

import numpy as np


class FMRIPrepLoader:
    MOTION = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z")
    CONFOUND_STRATEGIES = ("6P", "9P", "24P", "36P", "aCompCor", "24P+aCompCor")
    MNI_SPACES = ("MNI152NLin2009cAsym", "MNI152NLin6Asym")

    def __init__(self, derivatives_dir):
        self.root = os.path.abspath(derivatives_dir)
        self.subjects = []

    @staticmethod
    def looks_like_fmriprep(path):
        if not path or not os.path.isdir(path):
            return False
        root = Path(path)
        if any(root.rglob("*_desc-preproc_bold.nii*")):
            return True
        description = root / "dataset_description.json"
        if description.is_file():
            try:
                meta = json.loads(description.read_text(encoding="utf-8"))
                return "fmriprep" in json.dumps(meta.get("GeneratedBy", meta)).lower()
            except (ValueError, OSError):
                pass
        return False

    def detect_subjects(self):
        root = Path(self.root)
        if re.fullmatch(r"sub-[A-Za-z0-9]+", root.name):
            self.subjects = [root.name] if root.is_dir() else []
        else:
            self.subjects = sorted(p.name for p in root.glob("sub-*")
                                   if p.is_dir() and re.fullmatch(r"sub-[A-Za-z0-9]+", p.name))
        return self.subjects

    @staticmethod
    def _entities(path):
        return dict(token.split("-", 1) for token in Path(path).name.split("_")
                    if "-" in token)

    def list_bold(self, subject, space="MNI152NLin2009cAsym"):
        """List every scan deterministically; preserve session/run/space/resolution."""
        if subject not in self.detect_subjects():
            raise ValueError(f"未找到受试者 {subject}")
        root = Path(self.root)
        folder = root if root.name == subject else root / subject
        records = []
        for bold in sorted(folder.rglob("*_desc-preproc_bold.nii*")):
            if not bold.is_file() or not bold.name.endswith((".nii", ".nii.gz")):
                continue
            stem = re.sub(r"\.nii(?:\.gz)?$", "", str(bold))
            base = stem.removesuffix("_desc-preproc_bold")
            # Confounds describe the acquisition and do not carry spatial entities.
            conf_base = re.sub(r"_(?:space|res|den)-[^_]+", "", base)
            confounds = conf_base + "_desc-confounds_timeseries.tsv"
            if not os.path.isfile(confounds):
                # Multi-echo fMRIPrep outputs can share a run-level confounds table.
                confounds = re.sub(r"_echo-[^_]+", "", conf_base) + "_desc-confounds_timeseries.tsv"
            mask = base + "_desc-brain_mask.nii.gz"
            if not os.path.isfile(mask):
                mask = base + "_desc-brain_mask.nii"
            entities = self._entities(bold)
            records.append({
                "bold": str(bold),
                "confounds": confounds if os.path.isfile(confounds) else None,
                "mask": mask if os.path.isfile(mask) else None,
                "json": stem + ".json" if os.path.isfile(stem + ".json") else None,
                "space": entities.get("space", "native"),
                "entities": entities,
            })
        return sorted(records, key=lambda r: (r["space"] != space, r["bold"]))

    def find_bold(self, subject, space="MNI152NLin2009cAsym", bold_path=None):
        candidates = self.list_bold(subject, space)
        if bold_path:
            candidates = [r for r in candidates
                          if os.path.realpath(r["bold"]) == os.path.realpath(bold_path)]
        else:
            preferred = [r for r in candidates if r["space"] == space]
            candidates = preferred or [r for r in candidates if r["space"] in self.MNI_SPACES]
        if not candidates:
            raise ValueError(f"{subject} 未找到可用 MNI 空间 BOLD；请导出标准空间数据或重新选择扫描。")
        if len(candidates) > 1:
            raise ValueError(f"{subject} 有 {len(candidates)} 个 BOLD 扫描，请明确选择 session/run/分辨率。")
        files = candidates[0]
        if files["space"] not in self.MNI_SPACES:
            raise ValueError(f"当前 MNI ROI 分析不支持 {files['space']} 空间，请选择 MNI 空间 BOLD。")
        return files

    def read_metadata(self, files):
        """Read TR in seconds from the derivative JSON, then a unit-aware header."""
        import nibabel as nib
        meta = {}
        if files.get("json"):
            with open(files["json"], encoding="utf-8") as handle:
                meta = json.load(handle)
        img = nib.load(files["bold"])
        if len(img.shape) != 4 or img.shape[3] < 2:
            raise ValueError(f"BOLD 必须是至少含 2 个时间点的 4D 数据，实际为 {img.shape}")
        if "RepetitionTime" in meta:
            tr = meta["RepetitionTime"]
            source = "BOLD JSON RepetitionTime"
        else:
            unit = img.header.get_xyzt_units()[1]
            scale = {"sec": 1.0, "msec": 0.001, "usec": 0.000001}.get(unit)
            if scale is None:
                raise ValueError("缺少 RepetitionTime，且 NIfTI 时间单位未知；无法确定 TR。")
            tr = float(img.header.get_zooms()[3]) * scale
            source = f"NIfTI header ({unit})"
        if isinstance(tr, bool) or not isinstance(tr, (int, float)) or not np.isfinite(tr) or tr <= 0:
            raise ValueError(f"无效 TR: {tr!r}，RepetitionTime 必须是正数（秒）。")
        return {"metadata": meta, "TR": float(tr), "TR_source": source,
                "shape": list(img.shape), "voxel_size": list(map(float, img.header.get_zooms()[:3]))}

    def _read_confounds_tsv(self, tsv_path):
        with open(tsv_path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
        if len(rows) < 2:
            raise ValueError("confounds TSV 为空或没有数据行。")
        header = rows[0]
        if len(set(header)) != len(header) or not all(header):
            raise ValueError("confounds TSV 列名为空或重复。")
        data = []
        for line, row in enumerate(rows[1:], 2):
            if len(row) != len(header):
                raise ValueError(f"confounds TSV 第 {line} 行列数与表头不一致。")
            try:
                data.append([np.nan if v.strip().lower() in ("n/a", "nan", "") else float(v) for v in row])
            except ValueError as exc:
                raise ValueError(f"confounds TSV 第 {line} 行存在非数值内容。") from exc
        return header, np.asarray(data, dtype=float)

    @staticmethod
    def _column(header, data, name):
        if name not in header:
            raise ValueError(f"confounds 缺少必需列: {name}")
        values = data[:, header.index(name)].copy()
        # fMRIPrep defines the first derivative/FD sample as n/a.
        if np.isnan(values[0]) and ("derivative1" in name or name == "framewise_displacement"):
            values[0] = 0.0
        if not np.all(np.isfinite(values)):
            raise ValueError(f"confounds 列 {name} 存在缺失值或非有限值。")
        return values

    def build_confound_matrix(self, tsv_path, strategy="24P"):
        if strategy not in self.CONFOUND_STRATEGIES:
            raise ValueError(f"不支持的 confound 策略: {strategy}")
        header, data = self._read_confounds_tsv(tsv_path)
        names = list(self.MOTION)
        if strategy in ("9P", "36P"):
            names += ["white_matter", "csf", "global_signal"]
        cols = [self._column(header, data, name) for name in names]
        if strategy in ("24P", "36P", "24P+aCompCor"):
            derivs, squares, deriv_squares = [], [], []
            for name, values in zip(names, cols):
                def supplied_or(suffix, fallback):
                    key = name + suffix
                    return self._column(header, data, key) if key in header else fallback
                deriv = supplied_or("_derivative1", np.r_[0.0, np.diff(values)])
                derivs.append(deriv)
                squares.append(supplied_or("_power2", values ** 2))
                deriv_squares.append(supplied_or("_derivative1_power2", deriv ** 2))
            cols += derivs + squares + deriv_squares
        if strategy in ("aCompCor", "24P+aCompCor"):
            cols += [self._column(header, data, f"a_comp_cor_{i:02d}") for i in range(6)]
        return np.column_stack(cols)

    def get_fd(self, tsv_path):
        header, data = self._read_confounds_tsv(tsv_path)
        values = self._column(header, data, "framewise_displacement")
        if np.any(values < 0):
            raise ValueError("framewise_displacement 不应包含负值。")
        return values

    def clean_bold(self, files, output_dir, strategy="24P", tr=None, TR=None,
                   bandpass=(0.01, 0.1), fwhm=6.0, progress_cb=None):
        import nibabel as nib
        from nilearn.image import clean_img, smooth_img
        cb = progress_cb or (lambda p, m: None)
        info = self.read_metadata(files)
        effective_tr = TR if TR is not None else tr
        if effective_tr is not None and not np.isclose(effective_tr, info["TR"]):
            raise ValueError("传入 TR 与 BOLD 元数据不一致。")
        tr = info["TR"]
        low, high = bandpass
        if not (0 < low < high < 0.5 / tr):
            raise ValueError(f"带通范围 {bandpass} Hz 必须低于 Nyquist 频率 {0.5 / tr:g} Hz (TR={tr:g}s)。")
        if not np.isfinite(fwhm) or fwhm < 0:
            raise ValueError("FWHM 必须是非负有限数值。")
        if not files.get("confounds"):
            raise ValueError("未找到与当前扫描匹配的 confounds_timeseries.tsv，无法执行所选回归策略。")
        confounds = self.build_confound_matrix(files["confounds"], strategy)
        if confounds.shape[0] != info["shape"][3]:
            raise ValueError(f"confounds 行数 ({confounds.shape[0]}) 与 BOLD 时间点数 ({info['shape'][3]}) 不一致。")
        cb(30, f"加载 fMRIPrep BOLD ({files.get('space', '?')}, TR={tr:g}s)...")
        img = nib.load(files["bold"])
        raw = img.get_fdata(dtype=np.float32)
        if not np.isfinite(raw).all():
            raise ValueError("BOLD 存在 NaN/Inf，请检查输入数据。")
        if files.get("mask"):
            mask_img = nib.load(files["mask"])
            if mask_img.shape != img.shape[:3] or not np.allclose(mask_img.affine, img.affine, atol=1e-4):
                raise ValueError("脑掩膜与 BOLD 的尺寸或 affine 不一致。")
            mask_data = mask_img.get_fdata()
            if not np.isfinite(mask_data).all():
                raise ValueError("脑掩膜存在 NaN/Inf。")
            mask = mask_data > 0.5
        else:
            cb(31, "未提供脑掩膜，使用强度阈值估计；请检查覆盖范围。")
            mean = raw.mean(axis=3)
            positive = mean[mean > 0]
            if not positive.size:
                raise ValueError("BOLD 没有正值信号，无法估计脑掩膜。")
            mask = mean >= np.percentile(positive, 40)
        if not mask.any():
            raise ValueError("脑掩膜为空。")
        cb(36, f"confound 回归 ({strategy}, {confounds.shape[1]} 列) + 带通滤波...")
        cleaned = clean_img(img, detrend=True, standardize="zscore_sample",
                            confounds=confounds, low_pass=high, high_pass=low, t_r=tr,
                            mask_img=nib.Nifti1Image(mask.astype(np.uint8), img.affine),
                            ensure_finite=True)
        if fwhm > 0:
            cb(38, f"空间平滑 FWHM={fwhm:g}mm...")
            cleaned = smooth_img(cleaned, fwhm)
        # nilearn can inherit the integer mask header when unmasking. Persisting
        # that header would quantize cleaned signals and disagree with the .npy.
        cleaned.set_data_dtype(np.float32)
        cleaned.header.set_xyzt_units(img.header.get_xyzt_units()[0], "sec")
        cleaned.header.set_zooms((*img.header.get_zooms()[:3], tr))
        os.makedirs(output_dir, exist_ok=True)
        out = os.path.join(output_dir, "preprocessed_fmriprep.nii.gz")
        cb(39, "保存清洗结果...")
        nib.save(cleaned, out)
        np.save(os.path.join(output_dir, "brain_mask.npy"), mask)
        np.save(os.path.join(output_dir, "ts_raw_brain.npy"), raw[mask])
        np.save(os.path.join(output_dir, "data_preprocessed.npy"), cleaned.get_fdata(dtype=np.float32))
        with open(os.path.join(output_dir, "fmriprep_provenance.json"), "w", encoding="utf-8") as handle:
            json.dump({**info, "files": files, "confound_strategy": strategy,
                       "n_confounds": confounds.shape[1], "bandpass_hz": list(bandpass),
                       "fwhm_mm": fwhm, "mask_source": "fmriprep" if files.get("mask") else "intensity_estimate"},
                      handle, ensure_ascii=False, indent=2)
        cb(40, "fMRIPrep 数据清洗完成")
        return out
