"""Secret-file loader: reject symlinks and group/other-accessible files."""

import os

import pytest

from oqtopus_cloud.ops.secrets import InsecureSecretFile, load_secret_file


def _write(path, content, mode):
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, mode)


def test_reads_0600_file(tmp_path):
    p = tmp_path / "secret"
    _write(p, "hunter2\n", 0o600)
    assert load_secret_file(str(p)) == "hunter2"


def test_reads_0400_file(tmp_path):
    p = tmp_path / "secret"
    _write(p, "ro", 0o400)
    assert load_secret_file(str(p)) == "ro"


def test_rejects_group_or_other_accessible(tmp_path):
    for mode in (0o640, 0o604, 0o644, 0o660):
        p = tmp_path / f"s_{mode}"
        _write(p, "x", mode)
        with pytest.raises(InsecureSecretFile):
            load_secret_file(str(p))


def test_rejects_symlink(tmp_path):
    real = tmp_path / "real"
    _write(real, "x", 0o600)
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(InsecureSecretFile):
        load_secret_file(str(link))


def test_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_secret_file(str(tmp_path / "nope"))
