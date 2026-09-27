import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from core.advanced_preprocessing import PipelineConfig
from core.analyzer import BrainAnalyzer
from core.cohort_analyzer import CohortAnalyzer, Subject
from core.runtime import AnalysisCancelled, create_run_directory


def test_configuration_does_not_mutate_defaults(tmp_path):
    configured = PipelineConfig(str(tmp_path), {"nuisance_regression": {"gsr": True}})
    assert configured.cfg["nuisance_regression"]["gsr"]
    assert not PipelineConfig(str(tmp_path)).cfg["nuisance_regression"]["gsr"]
    assert not PipelineConfig.DEFAULT_CONFIG["nuisance_regression"]["gsr"]


def test_separate_run_directories_preserve_existing_output(tmp_path):
    first = Path(create_run_directory(tmp_path))
    (first / "result.txt").write_text("previous result")
    second = Path(create_run_directory(tmp_path))
    assert first != second
    assert (first / "result.txt").read_text() == "previous result"


def test_cancellation_escapes_pipeline_exception_handlers(derivative_factory, tmp_path):
    source = derivative_factory()
    stop = [False]
    def progress(pct, message):
        if pct == 10:
            stop[0] = True
    analyzer = BrainAnalyzer(None, str(tmp_path / "out"), progress_cb=progress,
                             fmriprep_dir=source["root"], should_stop=lambda: stop[0])
    with pytest.raises(AnalysisCancelled):
        analyzer.run_full_pipeline({})
    assert not (tmp_path / "out" / "results" / "preprocessed_fmriprep.nii.gz").exists()


def test_multiple_subjects_never_default_to_first(derivative_factory, tmp_path):
    source = derivative_factory(subject="sub-01")
    derivative_factory(subject="sub-02")
    analyzer = BrainAnalyzer(None, str(tmp_path / "out"), fmriprep_dir=source["root"])
    with pytest.raises(RuntimeError, match="明确选择受试者"):
        analyzer.run_full_pipeline({})


def test_cohort_cancellation_resets_previous_results_and_exports(tmp_path, monkeypatch):
    class CancelledAnalyzer:
        def __init__(self, **kwargs):
            pass
        def run_full_pipeline(self, options):
            raise AnalysisCancelled()
    monkeypatch.setattr("core.analyzer.BrainAnalyzer", CancelledAnalyzer)
    subjects = [Subject("sub-01", "unused"), Subject("sub-02", "unused")]
    for subject in subjects:
        subject.status, subject.results, subject.qc_score = "done", {"qc_metrics": {"QC_score": 100}}, 100
    cohort = CohortAnalyzer(subjects, str(tmp_path), {})
    np.save(Path(cohort.group_dir) / "group_mean_FC.npy", np.eye(2))
    result = cohort.run()
    assert result["cancelled"]
    assert result["n_done"] == result["n_failed"] == 0
    assert result["n_cancelled"] == result["n_pending"] == 1
    assert result["group"]["n"] == 0
    assert [s.status for s in subjects] == ["cancelled", "pending"]
    assert subjects[1].results is None
    assert Path(result["csv"]).exists()
    assert not (Path(cohort.group_dir) / "group_mean_FC.npy").exists()


def test_cohort_rejects_duplicate_and_unsafe_ids(tmp_path):
    for ids in [("same", "same"), ("../outside",), ("_group",)]:
        with pytest.raises(ValueError):
            CohortAnalyzer([Subject(s, "unused") for s in ids], str(tmp_path), {})


def test_same_shape_different_roi_order_not_averaged(tmp_path):
    subjects = [Subject("one", "unused"), Subject("two", "unused")]
    cohort = CohortAnalyzer(subjects, str(tmp_path), {})
    for i, subject in enumerate(subjects):
        folder = tmp_path / subject.subject_id / "results"
        folder.mkdir(parents=True)
        np.save(folder / "FC_pearson.npy", np.eye(2))
        (folder / "roi_names.json").write_text(json.dumps(["a", "b"] if i == 0 else ["b", "a"]))
    assert cohort._average_fc(subjects) is None


def test_out_of_coverage_rois_raise_instead_of_nan(derivative_factory, tmp_path):
    source = derivative_factory()
    analyzer = BrainAnalyzer(None, str(tmp_path / "out"), fmriprep_dir=source["root"])
    np.save(Path(analyzer.results_dir) / "data_preprocessed.npy", nib.load(source["bold"]).get_fdata())
    with pytest.raises(ValueError, match="ROI"):
        analyzer.compute_functional_connectivity(source["bold"])
    assert not (Path(analyzer.results_dir) / "FC_pearson.npy").exists()


def test_synthetic_fmriprep_pipeline_and_bilingual_reports(derivative_factory, tmp_path):
    affine = np.diag([10., 10., 10., 1.])
    affine[:3, 3] = [-100, -120, -80]
    source = derivative_factory(nt=100, shape=(21, 25, 21), affine=affine)
    out = tmp_path / "out"
    analyzer = BrainAnalyzer(None, str(out), fmriprep_dir=source["root"])
    result = analyzer.run_full_pipeline({"alff": False, "reho": False, "dynamic": True,
                                         "carpet_plot": False, "pdf": True, "word": True,
                                         "bilingual": True, "confound_strategy": "24P+aCompCor"})
    assert result["qc_metrics"]["TR_s"] == 0.8
    assert result["scan_params"]["TR"] == 0.8
    assert np.isfinite(result["fc"]["matrix"]).all()
    assert len(result["reports"]) == 4
    assert all(Path(path).stat().st_size > 1000 for path in result["reports"].values())
    snapshot = json.loads(Path(result["reproducibility"]["pipeline_snap"]).read_text())
    assert snapshot["config"]["nuisance_regression"]["strategy"] == "24P+aCompCor"
    assert snapshot["config"]["input"]["TR_s"] == 0.8
    import docx
    document = docx.Document(result["reports"]["word"])
    text = "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    assert "24P+aCompCor" in text and "0.8 s" in text
    assert "丢弃前5TR" not in text
