# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_START ===
"""strip_anchors 는 '마커인 줄'만 지워야 한다 (적대 리뷰 CRITICAL).

예전엔 `=== ANCHOR:` 를 포함한 아무 줄이나 지웠다. `vib scan --auto` 가
검증 문제 파일에 이 함수를 돌리므로, 문자열 리터럴에 마커 예시를 담은
정상 코드가 통째로 사라진다 — 복구 불가능한 손실이다. 검증 항목이 늘어날수록
이 삭제 경로에 들어오는 파일도 늘어난다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import is_anchor_marker_line, strip_anchors

MARKER = "=" * 3 + " ANCHOR: {name} " + "=" * 3


def _write(tmp_path: Path, name: str, lines: list[str]) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTKEEPSREALCODE_START ===
class TestKeepsRealCode:
    def test_string_literal_containing_marker_survives(self, tmp_path: Path) -> None:
        literal = 'SAMPLE = "# ' + MARKER.format(name="FOO_START") + '"'
        p = _write(
            tmp_path,
            "mod.py",
            [
                "# " + MARKER.format(name="MOD_START"),
                literal,
                "x = 1",
                "# " + MARKER.format(name="MOD_END"),
            ],
        )
        assert strip_anchors(p) is True
        remaining = p.read_text(encoding="utf-8")
        assert literal in remaining
        assert "x = 1" in remaining
        assert "MOD_START" not in remaining

    def test_marker_after_code_on_same_line_survives(self, tmp_path: Path) -> None:
        code = 'const s = "x";  // ' + MARKER.format(name="B_END")
        p = _write(
            tmp_path,
            "mod.ts",
            ["// " + MARKER.format(name="B_START"), code, "// " + MARKER.format(name="B_END")],
        )
        _ = strip_anchors(p)
        assert code in p.read_text(encoding="utf-8")

    def test_no_change_when_only_literals_present(self, tmp_path: Path) -> None:
        literal = 'SAMPLE = "# ' + MARKER.format(name="FOO_START") + '"'
        p = _write(tmp_path, "only.py", [literal, "y = 2"])
        assert strip_anchors(p) is False
        assert literal in p.read_text(encoding="utf-8")


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTKEEPSREALCODE_END ===


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTREMOVESALLMARKERFORMS_START ===
class TestRemovesAllMarkerForms:
    """재삽입 전 청소이므로 읽히지 않는 마커도 함께 걷어낸다."""

    def test_canonical_legacy_and_malformed_all_removed(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "mixed.py",
            [
                "# " + MARKER.format(name="OK_START"),
                "# ANCHOR: LEGACY_START",
                "# " + "=" * 3 + " ANCHOR: BROKEN_START",
                "keep = 1",
                "# " + MARKER.format(name="OK_END"),
            ],
        )
        assert strip_anchors(p) is True
        remaining = p.read_text(encoding="utf-8")
        assert remaining.strip() == "keep = 1"


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTREMOVESALLMARKERFORMS_END ===


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTISANCHORMARKERLINE_START ===
class TestIsAnchorMarkerLine:
    def test_marker_lines(self) -> None:
        assert is_anchor_marker_line("# " + MARKER.format(name="A_START"))
        assert is_anchor_marker_line("    // " + MARKER.format(name="A_END"))
        assert is_anchor_marker_line("# ANCHOR: A_START")
        assert is_anchor_marker_line("# " + "=" * 3 + " ANCHOR: A_START")

    def test_non_marker_lines(self) -> None:
        assert not is_anchor_marker_line('s = "# ' + MARKER.format(name="A_START") + '"')
        assert not is_anchor_marker_line("x = 1")
        assert not is_anchor_marker_line("# 앵커 경계(ANCHOR: NAME_START)를 지키세요")


# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_TESTISANCHORMARKERLINE_END ===
# === ANCHOR: TEST_STRIP_ANCHORS_LINE_SCOPE_END ===
