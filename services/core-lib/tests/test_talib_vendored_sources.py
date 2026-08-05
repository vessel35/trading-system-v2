"""Protect every vendored TA-Lib calculation source from silent changes."""

from __future__ import annotations

import hashlib
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_VENDORED_ROOT = _REPOSITORY_ROOT / "third_party/ta-lib"
_MANIFEST_PATH = _VENDORED_ROOT / "SHA256SUMS"

_EXPECTED_PATTERN_SOURCES = frozenset(
    f"src/ta_func/{filename}"
    for filename in """
        ta_CDL2CROWS.c
        ta_CDL3BLACKCROWS.c
        ta_CDL3INSIDE.c
        ta_CDL3LINESTRIKE.c
        ta_CDL3OUTSIDE.c
        ta_CDL3STARSINSOUTH.c
        ta_CDL3WHITESOLDIERS.c
        ta_CDLABANDONEDBABY.c
        ta_CDLADVANCEBLOCK.c
        ta_CDLBELTHOLD.c
        ta_CDLBREAKAWAY.c
        ta_CDLCLOSINGMARUBOZU.c
        ta_CDLCONCEALBABYSWALL.c
        ta_CDLCOUNTERATTACK.c
        ta_CDLDARKCLOUDCOVER.c
        ta_CDLDOJI.c
        ta_CDLDOJISTAR.c
        ta_CDLDRAGONFLYDOJI.c
        ta_CDLENGULFING.c
        ta_CDLEVENINGDOJISTAR.c
        ta_CDLEVENINGSTAR.c
        ta_CDLGAPSIDESIDEWHITE.c
        ta_CDLGRAVESTONEDOJI.c
        ta_CDLHAMMER.c
        ta_CDLHANGINGMAN.c
        ta_CDLHARAMI.c
        ta_CDLHARAMICROSS.c
        ta_CDLHIGHWAVE.c
        ta_CDLHIKKAKE.c
        ta_CDLHIKKAKEMOD.c
        ta_CDLHOMINGPIGEON.c
        ta_CDLIDENTICAL3CROWS.c
        ta_CDLINNECK.c
        ta_CDLINVERTEDHAMMER.c
        ta_CDLKICKING.c
        ta_CDLKICKINGBYLENGTH.c
        ta_CDLLADDERBOTTOM.c
        ta_CDLLONGLEGGEDDOJI.c
        ta_CDLLONGLINE.c
        ta_CDLMARUBOZU.c
        ta_CDLMATCHINGLOW.c
        ta_CDLMATHOLD.c
        ta_CDLMORNINGDOJISTAR.c
        ta_CDLMORNINGSTAR.c
        ta_CDLONNECK.c
        ta_CDLPIERCING.c
        ta_CDLRICKSHAWMAN.c
        ta_CDLRISEFALL3METHODS.c
        ta_CDLSEPARATINGLINES.c
        ta_CDLSHOOTINGSTAR.c
        ta_CDLSHORTLINE.c
        ta_CDLSPINNINGTOP.c
        ta_CDLSTALLEDPATTERN.c
        ta_CDLSTICKSANDWICH.c
        ta_CDLTAKURI.c
        ta_CDLTASUKIGAP.c
        ta_CDLTHRUSTING.c
        ta_CDLTRISTAR.c
        ta_CDLUNIQUE3RIVER.c
        ta_CDLUPSIDEGAP2CROWS.c
        ta_CDLXSIDEGAP3METHODS.c
    """.split()
)
_EXPECTED_SHARED_SOURCES = frozenset(
    {
        "src/ta_common/ta_global.c",
        "src/ta_func/ta_utility.h",
    }
)
_EXPECTED_INDICATOR_SOURCES = frozenset(
    {
        "src/ta_func/ta_HT_DCPERIOD.c",
        "src/ta_func/ta_HT_DCPHASE.c",
        "src/ta_func/ta_HT_PHASOR.c",
        "src/ta_func/ta_HT_SINE.c",
        "src/ta_func/ta_HT_TRENDLINE.c",
        "src/ta_func/ta_HT_TRENDMODE.c",
        "src/ta_func/ta_MAMA.c",
    }
)


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


def test_vendored_talib_sources_match_manifest() -> None:
    metadata, hashes = _read_manifest()

    assert metadata == {
        "Repository": "https://github.com/TA-Lib/ta-lib",
        "Tag": "v0.7.1",
        "Commit": "2247d599bddf37ed37e3a709371517e46efc66f6",
        "Scope": "TA-Lib calculation sources vendored with original paths",
        "Candlestick pattern source count": "61",
        "Shared source count": "2",
        "Hilbert indicator source count": "7",
    }

    manifest_paths = set(hashes)
    vendored_source_paths = {
        path.relative_to(_VENDORED_ROOT).as_posix()
        for path in (_VENDORED_ROOT / "src").rglob("*")
        if path.is_file()
    }
    assert len(_EXPECTED_PATTERN_SOURCES) == 61
    assert len(_EXPECTED_SHARED_SOURCES) == 2
    assert len(_EXPECTED_INDICATOR_SOURCES) == 7

    expected_paths = (
        _EXPECTED_PATTERN_SOURCES | _EXPECTED_SHARED_SOURCES | _EXPECTED_INDICATOR_SOURCES
    )
    assert len(expected_paths) == 70
    assert manifest_paths == expected_paths
    assert vendored_source_paths == expected_paths
    assert (_VENDORED_ROOT / "LICENSE").is_file()

    for relative_path, expected_digest in hashes.items():
        assert len(expected_digest) == 64
        assert expected_digest == expected_digest.lower()
        int(expected_digest, 16)
        actual_digest = hashlib.sha256((_VENDORED_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_digest == expected_digest, f"SHA-256 mismatch: {relative_path}"
