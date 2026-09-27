import time

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from core.runtime import AnalysisCancelled
from gui.main_window import AnalysisWorker, MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    monkeypatch.setattr("gui.main_window.ClinicalWarningDialog.exec_", lambda self: QDialog.Accepted)
    monkeypatch.setattr("gui.main_window.QMessageBox.information", lambda *args: None)
    win = MainWindow()
    yield win
    win.close()


def test_gui_requires_run_selection_and_preserves_cohort_subject_id(window, derivative_factory, monkeypatch):
    source = derivative_factory(run="01")
    derivative_factory(run="02")
    monkeypatch.setattr("gui.main_window.QFileDialog.getExistingDirectory", lambda *args: source["root"])
    window.chk_use_fmriprep.setChecked(True)
    window._select_fmriprep()
    assert window.cmb_fp_subject.currentText() == "sub-01"
    assert window.cmb_fp_scan.count() == 3
    assert window.cmb_fp_scan.currentData() is None
    window.cmb_fp_scan.setCurrentIndex(2)
    assert "run-02" in window.cmb_fp_scan.currentData()
    window._cohort_import_fmriprep(source["root"])
    window._cohort_finished({"subjects": [{"subject_id": "sub-01", "status": "done"}]})
    assert window.cohort_subjects[0][3] == "sub-01"
    assert window.cohort_table.item(0, 3).text() == "done"


def test_worker_cooperative_cancel_has_no_success_or_error_signal(app, monkeypatch, tmp_path):
    class SlowAnalyzer:
        def __init__(self, *args, **kwargs):
            self.should_stop = kwargs["should_stop"]
        def run_full_pipeline(self, options):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.should_stop():
                    raise AnalysisCancelled()
                time.sleep(0.005)
            return {}
    monkeypatch.setattr("gui.main_window.BrainAnalyzer", SlowAnalyzer)
    worker = AnalysisWorker("unused", str(tmp_path), {})
    events = []
    worker.cancelled.connect(lambda: events.append("cancelled"))
    worker.completed.connect(lambda r: events.append("completed"))
    worker.error.connect(lambda e: events.append("error"))
    worker.start()
    worker.requestInterruption()
    assert worker.wait(4000)
    app.processEvents()
    assert events == ["cancelled"]


def test_single_scan_selects_and_multiple_subjects_require_choice(window, derivative_factory, monkeypatch):
    source = derivative_factory()
    monkeypatch.setattr("gui.main_window.QFileDialog.getExistingDirectory", lambda *args: source["root"])
    window._select_fmriprep()
    assert window.cmb_fp_scan.currentData() == source["bold"]
    derivative_factory(subject="sub-02")
    window._select_fmriprep()
    assert window.cmb_fp_subject.currentIndex() == -1
    assert window.cmb_fp_scan.count() == 0
