"""Tests for `i2e_core.io_utils`."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core import io_utils


def test_atomic_write_creates_file(tmp_path: Path):
    p = tmp_path / "out.txt"
    io_utils.atomic_write(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"


def test_atomic_write_replaces_existing(tmp_path: Path):
    p = tmp_path / "out.txt"
    p.write_text("old", encoding="utf-8")
    io_utils.atomic_write(p, "new")
    assert p.read_text(encoding="utf-8") == "new"


def test_atomic_write_leaves_original_on_failure(tmp_path: Path, monkeypatch):
    p = tmp_path / "out.txt"
    p.write_text("original", encoding="utf-8")

    real_replace = io_utils.os.replace

    def boom(src, dst):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(io_utils.os, "replace", boom)
    with pytest.raises(OSError):
        io_utils.atomic_write(p, "new content")
    assert p.read_text(encoding="utf-8") == "original"
    # restore for cleanliness even though monkeypatch undoes it
    monkeypatch.setattr(io_utils.os, "replace", real_replace)


def test_dump_yaml_preserves_key_order():
    out = io_utils.dump_yaml({"b": 1, "a": 2})
    assert out == "b: 1\na: 2\n"


def test_load_yaml_roundtrip(tmp_path: Path):
    p = tmp_path / "x.yaml"
    p.write_text("k1: v1\nk2: 2\n", encoding="utf-8")
    assert io_utils.load_yaml(p) == {"k1": "v1", "k2": 2}


def test_atomic_write_bytes(tmp_path: Path):
    p = tmp_path / "b.bin"
    io_utils.atomic_write(p, b"\x00\x01\x02")
    assert p.read_bytes() == b"\x00\x01\x02"
