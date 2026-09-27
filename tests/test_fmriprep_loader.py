import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from core.fmriprep_loader import FMRIPrepLoader


def test_resolution_and_session_matching(derivative_factory):
    source = derivative_factory(session="A")
    loader = FMRIPrepLoader(source["root"])
    files = loader.find_bold("sub-01")
    assert files["confounds"] == source["confounds"]
    assert files["mask"] == source["mask"]
    assert files["entities"]["ses"] == "A"
    assert loader.read_metadata(files)["TR"] == 0.8
    subject_loader = FMRIPrepLoader(str(Path(source["root"]) / "sub-01"))
    assert subject_loader.detect_subjects() == ["sub-01"]
    assert subject_loader.find_bold("sub-01")["bold"] == source["bold"]


def test_multiple_runs_require_explicit_selection(derivative_factory):
    first = derivative_factory(run="01")
    second = derivative_factory(run="02")
    loader = FMRIPrepLoader(first["root"])
    with pytest.raises(ValueError, match="明确选择"):
        loader.find_bold("sub-01")
    assert loader.find_bold("sub-01", bold_path=second["bold"])["confounds"] == second["confounds"]


def test_native_space_is_not_used_with_mni_rois(derivative_factory):
    source = derivative_factory(space="T1w")
    loader = FMRIPrepLoader(source["root"])
    with pytest.raises(ValueError, match="MNI"):
        loader.find_bold("sub-01")
    with pytest.raises(ValueError, match="不支持"):
        loader.find_bold("sub-01", bold_path=source["bold"])


@pytest.mark.parametrize("strategy,columns", [("6P", 6), ("9P", 9), ("24P", 24),
                                              ("36P", 36), ("aCompCor", 12), ("24P+aCompCor", 30)])
def test_all_confound_strategies(derivative_factory, strategy, columns):
    source = derivative_factory()
    matrix = FMRIPrepLoader(source["root"]).build_confound_matrix(source["confounds"], strategy)
    assert matrix.shape == (80, columns)
    assert np.isfinite(matrix).all()


def test_unknown_and_incomplete_strategy_raise(derivative_factory):
    source = derivative_factory()
    loader = FMRIPrepLoader(source["root"])
    with pytest.raises(ValueError, match="不支持"):
        loader.build_confound_matrix(source["confounds"], "typo")
    path = Path(source["confounds"])
    path.write_text(path.read_text().replace("a_comp_cor_05", "missing_component"))
    with pytest.raises(ValueError, match="a_comp_cor_05"):
        loader.build_confound_matrix(str(path), "24P+aCompCor")


def test_single_row_and_single_column_tsv_shapes(tmp_path):
    path = tmp_path / "confounds.tsv"
    loader = FMRIPrepLoader(str(tmp_path))
    path.write_text("a\tb\n1\t2\n")
    assert loader._read_confounds_tsv(str(path))[1].shape == (1, 2)
    path.write_text("a\n1\n2\n")
    assert loader._read_confounds_tsv(str(path))[1].shape == (2, 1)


def test_existing_derivatives_are_used(tmp_path):
    path = tmp_path / "confounds.tsv"
    names = list(FMRIPrepLoader.MOTION) + ["trans_x_derivative1"]
    path.write_text("\t".join(names) + "\n" + "\t".join(["1"] * 6 + ["n/a"]) + "\n"
                    + "\t".join(["2"] * 6 + ["7"]) + "\n")
    matrix = FMRIPrepLoader(str(tmp_path)).build_confound_matrix(str(path), "24P")
    np.testing.assert_equal(matrix[:, 6], [0, 7])
    np.testing.assert_equal(matrix[:, 18], [0, 49])


def test_header_milliseconds_and_unknown_units(derivative_factory):
    source = derivative_factory()
    Path(source["json"]).unlink()
    source["json"] = None
    img = nib.load(source["bold"])
    replacement = nib.Nifti1Image(img.get_fdata(), img.affine, img.header)
    replacement.header.set_zooms((1, 1, 1, 800))
    replacement.header.set_xyzt_units("mm", "msec")
    nib.save(replacement, source["bold"])
    loader = FMRIPrepLoader(source["root"])
    assert loader.read_metadata(source)["TR"] == pytest.approx(0.8)
    replacement.header.set_xyzt_units("mm", "unknown")
    nib.save(replacement, source["bold"])
    with pytest.raises(ValueError, match="单位未知"):
        loader.read_metadata(source)


@pytest.mark.parametrize("tr", [0, -1, "2", True, None])
def test_invalid_json_tr_is_not_replaced_by_default(derivative_factory, tr):
    source = derivative_factory()
    Path(source["json"]).write_text(json.dumps({"RepetitionTime": tr}))
    with pytest.raises(ValueError, match="无效 TR"):
        FMRIPrepLoader(source["root"]).read_metadata(source)


def test_actual_nilearn_cleaning_and_provenance(derivative_factory, tmp_path):
    source = derivative_factory()
    out = tmp_path / "out"
    result = FMRIPrepLoader(source["root"]).clean_bold(source, str(out), strategy="24P+aCompCor", fwhm=0)
    data = nib.load(result).get_fdata()
    assert data.shape == (5, 6, 7, 80)
    assert np.isfinite(data).all()
    np.testing.assert_allclose(data.std(axis=3, ddof=1), 1, atol=1e-5)
    assert nib.load(result).get_data_dtype() == np.dtype("float32")
    np.testing.assert_array_equal(data, np.load(out / "data_preprocessed.npy"))
    provenance = json.loads((out / "fmriprep_provenance.json").read_text())
    assert provenance["TR"] == 0.8
    assert provenance["n_confounds"] == 30


@pytest.mark.parametrize("failure", ["rows", "mask", "missing", "nyquist", "nonfinite"])
def test_bad_inputs_fail_before_outputs(derivative_factory, tmp_path, failure):
    source = derivative_factory(tr=6 if failure == "nyquist" else 0.8)
    if failure == "rows":
        path = Path(source["confounds"])
        path.write_text("\n".join(path.read_text().splitlines()[:-1]))
    elif failure == "mask":
        nib.save(nib.Nifti1Image(np.ones((2, 2, 2)), np.eye(4)), source["mask"])
    elif failure == "missing":
        source["confounds"] = None
    elif failure == "nonfinite":
        img = nib.load(source["bold"])
        data = img.get_fdata()
        data[0, 0, 0, 0] = np.nan
        nib.save(nib.Nifti1Image(data, img.affine, img.header), source["bold"])
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        FMRIPrepLoader(source["root"]).clean_bold(source, str(out))
    assert not out.exists()


def test_missing_fd_not_reported_as_zero(derivative_factory):
    source = derivative_factory()
    loader = FMRIPrepLoader(source["root"])
    assert loader.get_fd(source["confounds"])[0] == 0
    path = Path(source["confounds"])
    path.write_text(path.read_text().replace("framewise_displacement", "absent"))
    with pytest.raises(ValueError, match="framewise_displacement"):
        loader.get_fd(str(path))


def test_output_header_uses_authoritative_json_tr(derivative_factory, tmp_path):
    source = derivative_factory(tr=2.0)
    Path(source["json"]).write_text(json.dumps({"RepetitionTime": 0.8}))
    result = FMRIPrepLoader(source["root"]).clean_bold(source, str(tmp_path / "out"), fwhm=0)
    img = nib.load(result)
    assert img.header.get_xyzt_units()[1] == "sec"
    assert img.header.get_zooms()[3] == pytest.approx(0.8)
