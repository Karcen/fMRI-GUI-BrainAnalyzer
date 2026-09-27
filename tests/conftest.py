import json
import os

import nibabel as nib
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")


@pytest.fixture
def derivative_factory(tmp_path):
    def make(subject="sub-01", run="01", space="MNI152NLin2009cAsym", res="2",
             nt=80, tr=0.8, shape=(5, 6, 7), affine=None, session=None):
        folder = tmp_path / "derivatives" / subject
        if session:
            folder /= f"ses-{session}"
        folder /= "func"
        folder.mkdir(parents=True, exist_ok=True)
        prefix = subject + (f"_ses-{session}" if session else "") + f"_task-rest_run-{run}"
        stem = f"{prefix}_space-{space}_res-{res}"
        bold = folder / f"{stem}_desc-preproc_bold.nii.gz"
        rng = np.random.default_rng(42)
        data = (100 + rng.normal(size=(*shape, nt))).astype(np.float32)
        affine = np.eye(4) if affine is None else affine
        img = nib.Nifti1Image(data, affine)
        img.header.set_zooms((*img.header.get_zooms()[:3], tr))
        img.header.set_xyzt_units("mm", "sec")
        nib.save(img, bold)
        sidecar = folder / f"{stem}_desc-preproc_bold.json"
        sidecar.write_text(json.dumps({"RepetitionTime": tr}))
        mask = folder / f"{stem}_desc-brain_mask.nii.gz"
        nib.save(nib.Nifti1Image(np.ones(shape, dtype=np.uint8), affine), mask)
        confounds = folder / f"{prefix}_desc-confounds_timeseries.tsv"
        names = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
                 "white_matter", "csf", "global_signal"] + [f"a_comp_cor_{i:02d}" for i in range(6)]
        names += ["framewise_displacement"]
        values = rng.normal(scale=0.01, size=(nt, len(names)))
        values[:, -1] = np.abs(values[:, -1])
        values[0, -1] = np.nan
        np.savetxt(confounds, values, delimiter="\t", header="\t".join(names), comments="")
        return {"root": str(tmp_path / "derivatives"), "subject": subject,
                "bold": str(bold), "confounds": str(confounds), "mask": str(mask),
                "json": str(sidecar), "space": space}
    return make
