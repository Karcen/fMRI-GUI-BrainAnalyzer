#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文献自动更新模块 · Literature Auto-Updater
==========================================
通过 NCBI PubMed E-utilities（官方免费 API，无需密钥）按「疾病 + 脑网络」
关键词检索最近数年的最新文献，用于报告第十章的文献对照。

隐私 / Privacy
--------------
本模块**只向 NCBI 发送疾病名称与通用神经科学检索词**（如 "major depressive
disorder resting-state functional connectivity"），**绝不发送任何受试者数据、
影像或分析结果**。所有网络调用可通过 enable=False 完全关闭。

离线兜底 / Offline fallback
---------------------------
无网络或请求失败时，get_recent_refs() 返回空列表，调用方回退到内置的
硬编码参考文献，不影响报告生成。
"""
import os
import json
import time
import ssl
import urllib.parse
import urllib.request
from datetime import datetime

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# 疾病键 → PubMed 检索式（脑网络 / 静息态 fMRI 语境）
DISEASE_QUERIES = {
    "MDD":  "major depressive disorder resting-state functional connectivity default mode network",
    "BD":   "bipolar disorder resting-state functional connectivity prefrontal amygdala",
    "SCZ":  "schizophrenia resting-state functional connectivity default mode network",
    "ADHD": "ADHD resting-state functional connectivity default mode dorsal attention",
    "ASD":  "autism spectrum disorder resting-state functional connectivity",
    "GAD":  "generalized anxiety disorder resting-state functional connectivity amygdala",
    "OCD":  "obsessive compulsive disorder cortico-striato-thalamic functional connectivity",
    "PTSD": "PTSD resting-state functional connectivity amygdala prefrontal",
    "AD":   "Alzheimer disease resting-state functional connectivity default mode network",
    "PD":   "Parkinson disease resting-state functional connectivity sensorimotor network",
}


class LiteratureUpdater:
    """按疾病抓取 PubMed 最新文献；带本地缓存与离线兜底。"""

    def __init__(self, cache_dir=None, cache_days=30, timeout=6, years=6):
        self.cache_dir = cache_dir or os.path.expanduser("~")
        self.cache_file = os.path.join(self.cache_dir, ".brain_analyzer_litcache.json")
        self.cache_days = cache_days      # 缓存有效期（天）
        self.timeout = timeout            # 单次请求超时（秒）
        self.years = years                # 只检索最近 N 年
        self._ctx = ssl.create_default_context()

    # ── 缓存 ──────────────────────────────────────────────────────────────
    def _load_cache(self) -> dict:
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self, cache: dict):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _fresh(self, entry: dict) -> bool:
        try:
            age = time.time() - float(entry.get("_ts", 0))
            return age < self.cache_days * 86400
        except Exception:
            return False

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _get(self, endpoint: str, params: dict):
        url = f"{EUTILS}/{endpoint}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "BrainAnalyzer/3.0"})
        with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as r:
            return json.loads(r.read().decode("utf-8"))

    # ── 核心检索 ────────────────────────────────────────────────────────────
    def fetch(self, query: str, retmax: int = 3) -> list:
        """检索 PubMed，返回 [{pmid,title,authors,journal,year}]。失败返回 []。"""
        try:
            yr_min = datetime.now().year - self.years
            es = self._get("esearch.fcgi", {
                "db": "pubmed", "term": query, "retmax": retmax,
                "sort": "date", "retmode": "json",
                "datetype": "pdat", "mindate": yr_min, "maxdate": 3000,
            })
            ids = es.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []
            time.sleep(0.34)   # 遵守 NCBI ≤3 req/s
            su = self._get("esummary.fcgi", {
                "db": "pubmed", "id": ",".join(ids), "retmode": "json",
            })
            res = su.get("result", {})
            out = []
            for pid in res.get("uids", []):
                d = res.get(pid, {})
                auth = d.get("authors", [])
                first = auth[0].get("name", "") if auth else ""
                etal = " et al." if len(auth) > 1 else ""
                pub = d.get("pubdate", "")
                year = pub.split(" ")[0] if pub else ""
                out.append({
                    "pmid": pid,
                    "title": d.get("title", "").rstrip("."),
                    "authors": f"{first}{etal}",
                    "journal": d.get("source", ""),
                    "year": year,
                })
            return out
        except Exception:
            return []

    # ── 便捷接口（按疾病键，带缓存） ─────────────────────────────────────────
    def get_recent_refs(self, disease_key: str, retmax: int = 3) -> list:
        """按疾病键返回最新文献；优先用新鲜缓存，否则联网抓取并写缓存。"""
        query = DISEASE_QUERIES.get(disease_key)
        if not query:
            return []
        cache = self._load_cache()
        entry = cache.get(disease_key)
        if entry and self._fresh(entry):
            return entry.get("refs", [])
        refs = self.fetch(query, retmax=retmax)
        if refs:
            cache[disease_key] = {"_ts": time.time(), "refs": refs}
            self._save_cache(cache)
        return refs

    @staticmethod
    def format_ref(ref: dict) -> str:
        """把一条文献格式化为紧凑引用串。"""
        parts = [p for p in (ref.get("authors"), ref.get("year"),
                             ref.get("journal")) if p]
        head = ", ".join(parts)
        return f"{head}. PMID:{ref.get('pmid','')}" if head else f"PMID:{ref.get('pmid','')}"

    def check_online(self) -> bool:
        """快速探测能否访问 PubMed（1 条最小查询）。"""
        try:
            self._get("einfo.fcgi", {"retmode": "json"})
            return True
        except Exception:
            return False
