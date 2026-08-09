# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_START ===
"""spans 가 광고하는 이름은 blocks 로도 읽을 수 있어야 한다.

extract_anchor_spans 는 같은 이름이 두 번 열리면 DUP, DUP_2 로 구분해
project map·MCP 에 내보낸다. 그런데 blocks/ranges 는 기본 이름만 만들어,
광고된 DUP_2 를 요청하면 "anchor not found" 가 돌아왔다 — PR #1 이 고친
"광고는 됐는데 읽히지 않는 앵커"와 같은 부류다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchor_blocks,
    extract_anchor_line_ranges,
    extract_anchor_spans,
    iter_anchor_blocks,
)

MARKER = "=" * 3 + " ANCHOR: {name} " + "=" * 3


def _m(name: str) -> str:
    return "# " + MARKER.format(name=name)


def _write(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "mod.py"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTSEQUENTIALDUPLICATES_START ===
class TestSequentialDuplicates:
    def _sample(self, tmp_path: Path) -> Path:
        return _write(
            tmp_path,
            [
                _m("DUP_START"),
                "first = 1",
                _m("DUP_END"),
                _m("DUP_START"),
                "second = 2",
                _m("DUP_END"),
            ],
        )

    def test_spans_and_blocks_expose_the_same_names(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        advertised = {str(s["name"]) for s in extract_anchor_spans(p)}
        assert advertised == {"DUP", "DUP_2"}
        assert advertised <= set(extract_anchor_blocks(p))

    def test_occurrence_order_matches_spans(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        blocks = extract_anchor_blocks(p)
        # 번호는 START 순서 — spans 와 동일해야 한다
        assert blocks["DUP"] == "first = 1"
        assert blocks["DUP_2"] == "second = 2"

    def test_line_ranges_agree_with_spans(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        ranges = extract_anchor_line_ranges(p)
        by_name = {str(s["name"]): (s["start"], s["end"]) for s in extract_anchor_spans(p)}
        assert ranges == by_name

    def test_only_filter_accepts_occurrence_name(self, tmp_path: Path) -> None:
        # MCP anchor_read_content 가 광고된 이름으로 조회하는 경로
        p = self._sample(tmp_path)
        blocks = extract_anchor_blocks(p, only={"DUP_2"})
        assert blocks == {"DUP_2": "second = 2"}

    def test_iter_matches_dict_extraction(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        assert dict(iter_anchor_blocks(p)) == extract_anchor_blocks(p)


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTSEQUENTIALDUPLICATES_END ===


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTNESTEDSAMENAME_START ===
class TestNestedSameName:
    def test_outer_keeps_the_base_name(self, tmp_path: Path) -> None:
        # A_START A_START A_END A_END — 바깥이 occurrence 1 이므로 A
        p = _write(
            tmp_path,
            [_m("A_START"), _m("A_START"), "inner = 1", _m("A_END"), _m("A_END")],
        )
        blocks = extract_anchor_blocks(p)
        assert set(blocks) == {"A", "A_2"}
        assert "inner = 1" in blocks["A"]
        assert blocks["A_2"] == "inner = 1"

    def test_single_occurrence_has_no_suffix(self, tmp_path: Path) -> None:
        p = _write(tmp_path, [_m("SOLO_START"), "x = 1", _m("SOLO_END")])
        assert set(extract_anchor_blocks(p)) == {"SOLO"}


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTNESTEDSAMENAME_END ===


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTNAMECOLLISION_START ===
class TestNameCollision:
    """occurrence 이름이 실제 앵커 이름과 부딪히면 안 된다.

    A 가 두 번 있으면 두 번째가 A_2 가 되는데, 파일에 진짜 A_2 앵커가 따로
    있으면 키가 겹쳐 한쪽이 조용히 덮인다 — MCP 가 요청과 다른 코드를 준다.
    """

    def _sample(self, tmp_path: Path) -> Path:
        return _write(
            tmp_path,
            [
                _m("A_START"),
                "first = 1",
                _m("A_END"),
                _m("A_2_START"),
                "real_a2 = 2",
                _m("A_2_END"),
                _m("A_START"),
                "second = 3",
                _m("A_END"),
            ],
        )

    def test_real_anchor_keeps_its_own_name(self, tmp_path: Path) -> None:
        blocks = extract_anchor_blocks(self._sample(tmp_path))
        assert blocks["A_2"] == "real_a2 = 2"

    def test_second_occurrence_skips_the_taken_name(self, tmp_path: Path) -> None:
        blocks = extract_anchor_blocks(self._sample(tmp_path))
        assert blocks["A"] == "first = 1"
        assert blocks["A_3"] == "second = 3"

    def test_no_block_is_silently_overwritten(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        blocks = extract_anchor_blocks(p)
        # 마커 쌍 3개 → 블록 3개. 겹치면 2개로 줄어든다.
        assert len(blocks) == 3
        assert sorted(blocks) == ["A", "A_2", "A_3"]

    def test_spans_and_blocks_still_agree_under_collision(self, tmp_path: Path) -> None:
        p = self._sample(tmp_path)
        advertised = {str(s["name"]) for s in extract_anchor_spans(p)}
        assert advertised == set(extract_anchor_blocks(p))
        assert advertised == set(extract_anchor_line_ranges(p))


# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_TESTNAMECOLLISION_END ===
# === ANCHOR: TEST_ANCHOR_DUPLICATE_OCCURRENCE_NAMES_END ===
