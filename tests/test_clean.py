import subprocess

import pytest
from deepracer import clean


class _Result:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.returncode = 0


def test_clean_oci_images_removes_only_deepracer(monkeypatch):
    calls = []

    def fake_run(argv):
        calls.append(argv)
        if argv[1] == "images":
            return _Result(
                "ghcr.io/uzairakbar/deepracer:v0 aaa111\n"
                "ubuntu:24.04 bbb222\n"
                "localhost/deepracer:dev ccc333\n"
            )
        return _Result()

    monkeypatch.setattr(clean, "_run", fake_run)
    monkeypatch.setattr(clean.shutil, "which", lambda b: "/usr/bin/" + b)

    clean._clean_oci_images("docker")

    removed = {c[3] for c in calls if c[1] == "rmi"}
    assert removed == {"aaa111", "ccc333"}


def test_clean_oci_images_skips_missing_binary(monkeypatch):
    monkeypatch.setattr(clean.shutil, "which", lambda b: None)
    monkeypatch.setattr(
        clean, "_run", lambda argv: pytest.fail("should not run anything")
    )
    clean._clean_oci_images("docker")


def test_clean_apptainer_images_removes_cached_sifs(monkeypatch, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    sif = scratch / "deepracer-abc123.sif"
    sif.write_bytes(b"sif")
    keep = scratch / "other.sif"
    keep.write_bytes(b"keep")

    monkeypatch.setattr(clean.os.path, "expanduser", lambda p: str(scratch))

    clean._clean_apptainer_images()

    assert not sif.exists()
    assert keep.exists()


def test_help_flag():
    result = subprocess.run(
        ["python3", "-m", "deepracer.clean", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--deep" in result.stdout
