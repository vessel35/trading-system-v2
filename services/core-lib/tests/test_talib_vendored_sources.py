"""Protect the vendored TA-Lib candlestick sources from silent changes."""

from __future__ import annotations

import hashlib
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_VENDORED_ROOT = _REPOSITORY_ROOT / "third_party/ta-lib"
_MANIFEST_PATH = _VENDORED_ROOT / "SHA256SUMS"


def _read_manifest() -> tuple[dict[str, str], dict[str, str]]:
    metadata: dict[str, str] = {}
    hashes: dict[str, str] = {}

    for line in _MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            name, separator, value = line.removeprefix("# ").partition(": ")
            assert separator, f"invalid manifest metadata: {line}"
            metadata[name] = value
            continue

        digest, separator, relative_path = line.partition("  ")
        assert separator, f"invalid manifest entry: {line}"
        assert relative_path not in hashes, f"duplicate manifest path: {relative_path}"
        hashes[relative_path] = digest

    return metadata, hashes


def test_vendored_talib_candlestick_sources_match_manifest() -> None:
    metadata, hashes = _read_manifest()

    assert metadata == {
        "Repository": "https://github.com/TA-Lib/ta-lib",
        "Tag": "v0.7.1",
        "Commit": "2247d599bddf37ed37e3a709371517e46efc66f6",
        "Scope": "63 candlestick calculation source files vendored with original paths",
    }

    manifest_paths = set(hashes)
    vendored_source_paths = {
        path.relative_to(_VENDORED_ROOT).as_posix()
        for path in (_VENDORED_ROOT / "src").rglob("*")
        if path.is_file()
    }
    pattern_paths = {
        path
        for path in manifest_paths
        if Path(path).parent.as_posix() == "src/ta_func"
        and Path(path).name.startswith("ta_CDL")
        and Path(path).suffix == ".c"
    }

    assert len(hashes) == 63
    assert len(pattern_paths) == 61
    assert manifest_paths - pattern_paths == {
        "src/ta_common/ta_global.c",
        "src/ta_func/ta_utility.h",
    }
    assert vendored_source_paths == manifest_paths
    assert (_VENDORED_ROOT / "LICENSE").is_file()

    for relative_path, expected_digest in hashes.items():
        assert len(expected_digest) == 64
        assert expected_digest == expected_digest.lower()
        int(expected_digest, 16)
        actual_digest = hashlib.sha256((_VENDORED_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_digest == expected_digest, f"SHA-256 mismatch: {relative_path}"
