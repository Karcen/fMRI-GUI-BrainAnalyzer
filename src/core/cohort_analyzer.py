#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
队列分析引擎 — 串行处理多个受试者，汇总组级统计并导出 CSV。

设计要点：
  · 每个受试者复用单人 BrainAnalyzer.run_full_pipeline()
  · 每人输出独立子目录 <output_dir>/<subject_id>/
  · 单人失败不影响队列继续（记录错误，跳过）
  · 全部完成后计算组级统计：QC 分布、FC 均值、FD 分布等
  · 导出 cohort_summary.csv（每人一行）+ group_stats.json
  · 预留扩展接口：组级 FC 对比、统计检验（后期）
"""
import os
import csv
import json
import traceback
import numpy as np


class Subject:
    """单个受试者的输入描述。"""

    def __init__(self, subject_id: str, input_path: str,
                 input_type: str = "dicom", fmriprep_subject: str = None):
        """
        subject_id      : 唯一标识（用于输出目录 / CSV 行）
        input_path      : DICOM 文件夹 或 fMRIPrep derivatives 目录
        input_type      : "dicom" | "fmriprep"
        fmriprep_subject: 当 input_type=fmriprep 且目录含多受试者时指定 sub-XXX
        """
        self.subject_id       = subject_id
        self.input_path       = input_path
        self.input_type       = input_type
        self.fmriprep_subject = fmriprep_subject
        # 运行时填充
        self.status   = "pending"   # pending | running | done | failed
        self.qc_score = None
        self.error    = None
        self.results  = None

    def to_row(self) -> dict:
        r = {
            "subject_id":  self.subject_id,
            "input_type":  self.input_type,
            "status":      self.status,
            "qc_score":    self.qc_score if self.qc_score is not None else "",
            "error":       (self.error or "")[:200],
        }
        return r


class CohortAnalyzer:
    """串行队列分析器。"""

    def __init__(self, subjects: list, output_dir: str, options: dict,
                 progress_cb=None, should_stop=None):
        """
        subjects    : list[Subject]
        output_dir  : 队列输出根目录
        options     : 传给单人管线的选项 dict
        progress_cb : fn(pct:int, msg:str)
        should_stop : fn() -> bool，返回 True 时在受试者间隔处中止
        """
        self.subjects    = subjects
        self.output_dir  = output_dir
        self.options     = options
        self.progress_cb = progress_cb or (lambda p, m: print(f"[{p:3d}%] {m}"))
        self.should_stop = should_stop or (lambda: False)
        os.makedirs(output_dir, exist_ok=True)
        self.group_dir = os.path.join(output_dir, "_group")
        os.makedirs(self.group_dir, exist_ok=True)

    # ── 主流程 ────────────────────────────────────────────────────────────────

    def run(self) -> dict:
        from core.analyzer import BrainAnalyzer

        n = len(self.subjects)
        if n == 0:
            raise RuntimeError("队列为空，请先添加受试者。")

        self.progress_cb(0, f"队列分析开始：{n} 个受试者（串行处理）")
        done, failed = 0, 0

        for i, subj in enumerate(self.subjects):
            if self.should_stop():
                self.progress_cb(0, "用户中止队列分析。")
                break

            base_pct = int(100 * i / n)
            subj.status = "running"
            self.progress_cb(
                base_pct, f"[{i+1}/{n}] 处理受试者 {subj.subject_id} ...")

            subj_out = os.path.join(self.output_dir, subj.subject_id)
            os.makedirs(subj_out, exist_ok=True)

            # 单人进度映射到队列全局进度区间 [base, next)
            def make_cb(base):
                span = 100.0 / n

                def _cb(p, m):
                    g = int(base + (p / 100.0) * span)
                    self.progress_cb(min(99, g),
                                     f"[{i+1}/{n}] {subj.subject_id}: {m}")
                return _cb

            try:
                if subj.input_type == "fmriprep":
                    analyzer = BrainAnalyzer(
                        dicom_path=None, output_dir=subj_out,
                        progress_cb=make_cb(base_pct),
                        fmriprep_dir=subj.input_path)
                    analyzer.fmriprep_subject = subj.fmriprep_subject
                else:
                    analyzer = BrainAnalyzer(
                        dicom_path=subj.input_path, output_dir=subj_out,
                        progress_cb=make_cb(base_pct))

                res = analyzer.run_full_pipeline(self.options)
                subj.results  = res
                subj.qc_score = res.get("qc_metrics", {}).get("QC_score")
                subj.status   = "done"
                done += 1
            except Exception as e:
                subj.status = "failed"
                subj.error  = str(e)
                failed += 1
                # 记录 traceback 到受试者目录
                try:
                    with open(os.path.join(subj_out, "error.log"),
                              "w", encoding="utf-8") as f:
                        f.write(traceback.format_exc())
                except Exception:
                    pass
                self.progress_cb(base_pct,
                                 f"[{i+1}/{n}] {subj.subject_id} 失败: {e}")

        # ── 组级汇总 ─────────────────────────────────────────────────────────
        self.progress_cb(99, "计算组级统计 + 导出 CSV ...")
        group = self.compute_group_stats()
        self.export_csv()
        self.progress_cb(100,
                         f"✓ 队列完成：成功 {done}，失败 {failed}，共 {n}")
        return {
            "n_total":   n,
            "n_done":    done,
            "n_failed":  failed,
            "group":     group,
            "csv":       os.path.join(self.group_dir, "cohort_summary.csv"),
            "subjects":  [s.to_row() for s in self.subjects],
        }

    # ── 组级统计 ──────────────────────────────────────────────────────────────

    def compute_group_stats(self) -> dict:
        done = [s for s in self.subjects if s.status == "done" and s.results]
        if not done:
            g = {"n": 0, "note": "无成功受试者，跳过组级统计"}
            self._save_json("group_stats.json", g)
            return g

        def collect(path_fn):
            vals = []
            for s in done:
                try:
                    v = path_fn(s.results)
                    if v is not None and np.isfinite(v):
                        vals.append(float(v))
                except Exception:
                    pass
            return np.array(vals) if vals else np.array([])

        def stat(arr):
            if arr.size == 0:
                return {"n": 0}
            return {
                "n":    int(arr.size),
                "mean": round(float(arr.mean()), 4),
                "std":  round(float(arr.std()), 4),
                "min":  round(float(arr.min()), 4),
                "max":  round(float(arr.max()), 4),
                "median": round(float(np.median(arr)), 4),
            }

        qc   = collect(lambda r: r.get("qc_metrics", {}).get("QC_score"))
        tsnr = collect(lambda r: r.get("qc_metrics", {}).get("tSNR_median"))
        fd   = collect(lambda r: r.get("qc_metrics", {}).get("FD_proxy_pct_mean"))
        dmn  = collect(lambda r: r.get("fc", {}).get("dmn_mean_fc"))
        sigma= collect(lambda r: r.get("graph", {}).get("small_world_sigma"))
        ge   = collect(lambda r: r.get("graph", {}).get("global_efficiency"))

        # 组级平均 FC 矩阵（若各人 ROI 数一致）
        group_fc = self._average_fc(done)

        group = {
            "n":                len(done),
            "QC_score":         stat(qc),
            "tSNR_median":      stat(tsnr),
            "FD_proxy_pct_mean":stat(fd),
            "DMN_internal_FC":  stat(dmn),
            "small_world_sigma":stat(sigma),
            "global_efficiency":stat(ge),
            "group_fc_computed":group_fc is not None,
        }
        self._save_json("group_stats.json", group)
        return group

    def _average_fc(self, done: list):
        """若所有成功受试者 FC 维度一致，计算组平均 FC 矩阵并保存。"""
        mats = []
        for s in done:
            fc_path = os.path.join(self.output_dir, s.subject_id,
                                   "results", "FC_pearson.npy")
            if os.path.isfile(fc_path):
                try:
                    mats.append(np.load(fc_path))
                except Exception:
                    pass
        if len(mats) < 2:
            return None
        shapes = {m.shape for m in mats}
        if len(shapes) != 1:
            return None  # 维度不一致（不同 atlas），跳过
        stack = np.stack(mats, axis=0)
        mean_fc = stack.mean(axis=0)
        np.save(os.path.join(self.group_dir, "group_mean_FC.npy"), mean_fc)
        np.save(os.path.join(self.group_dir, "group_std_FC.npy"),
                stack.std(axis=0))
        return mean_fc.shape

    # ── 导出 ──────────────────────────────────────────────────────────────────

    def export_csv(self):
        """每个受试者一行，含核心指标。"""
        fields = ["subject_id", "input_type", "status", "qc_score",
                  "tSNR_median", "FD_mean", "DMN_FC", "sigma",
                  "global_efficiency", "error"]
        rows = []
        for s in self.subjects:
            r = s.to_row()
            qcm = (s.results or {}).get("qc_metrics", {})
            gm  = (s.results or {}).get("graph", {})
            fc  = (s.results or {}).get("fc", {})
            r["tSNR_median"]       = round(qcm.get("tSNR_median", 0), 3) if s.results else ""
            r["FD_mean"]           = round(qcm.get("FD_proxy_pct_mean", 0), 4) if s.results else ""
            r["DMN_FC"]            = round(fc.get("dmn_mean_fc", 0), 4) if s.results else ""
            r["sigma"]             = round(gm.get("small_world_sigma", 0), 3) if s.results else ""
            r["global_efficiency"] = round(gm.get("global_efficiency", 0), 3) if s.results else ""
            rows.append(r)

        csv_path = os.path.join(self.group_dir, "cohort_summary.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        return csv_path

    def _save_json(self, name, obj):
        with open(os.path.join(self.group_dir, name),
                  "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
