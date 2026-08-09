# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_START ===
"""validate 는 마커의 개수·중첩·형식 훼손을 실제로 잡아야 한다 (issue #5, #3).

기존 validator 는 이름의 집합 포함 여부만 봤다. 같은 이름의 START 2개 +
END 1개가 오류 없이 통과했는데, 추출은 안쪽 블록만 선택하므로 바깥 구간이
보호 없이 남는다. 검증이 통과했으니 사용자는 알 수 없다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    find_malformed_anchor_markers,
    has_anchor_markers,
    validate_anchor_file,
)

MARKER = "=" * 3 + " ANCHOR: {name} " + "=" * 3


def _write(tmp_path: Path, name: str, lines: list[str]) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _m(name: str, prefix: str = "#") -> str:
    return f"{prefix} {MARKER.format(name=name)}"


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTMULTIPLICITY_START ===
class TestMultiplicity:
    def test_duplicate_start_with_single_end_is_reported(self, tmp_path: Path) -> None:
        # 이슈 #5 의 정확한 재현: START 2 + END 1
        p = _write(
            tmp_path,
            "dup.py",
            [_m("A_START"), "outer = 1", _m("A_START"), "inner = 2", _m("A_END")],
        )
        problems = validate_anchor_file(p)
        assert any("A_START" in x and "END" in x for x in problems), problems

    def test_unpaired_end_is_reported(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "orphan.py", ["x = 1", _m("B_END")])
        problems = validate_anchor_file(p)
        assert any("B_END" in x for x in problems), problems

    def test_reports_line_number(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "line.py", ["x = 1", "y = 2", _m("C_START"), "z = 3"])
        problems = validate_anchor_file(p)
        assert any("3" in x and "C_START" in x for x in problems), problems

    def test_legitimate_nesting_is_not_an_error(self, tmp_path: Path) -> None:
        # 모듈 앵커 ⊃ 심볼 앵커는 정상이다. 이걸 오류로 보면 리포 전체가 빨개진다.
        p = _write(
            tmp_path,
            "nest.py",
            [
                _m("MOD_START"),
                _m("MOD_FN_START"),
                "def fn(): ...",
                _m("MOD_FN_END"),
                _m("MOD_END"),
            ],
        )
        assert validate_anchor_file(p) == []

    def test_crossing_anchors_are_reported(self, tmp_path: Path) -> None:
        """교차는 중첩이 아니다.

        P_START Q_START P_END Q_END 에서 블록 P 는 Q 의 여는 마커만 품는다.
        AI 가 P 를 고치면 Q 의 경계가 깨지는데, 짝은 맞으니 예전 validator 는
        통과시켰다. 완전히 포개지거나 완전히 떨어져 있어야 한다.
        """
        p = _write(
            tmp_path,
            "cross.py",
            [_m("P_START"), _m("Q_START"), "x = 1", _m("P_END"), _m("Q_END")],
        )
        problems = validate_anchor_file(p)
        assert any("교차" in x for x in problems), problems

    def test_sequential_anchors_are_not_an_error(self, tmp_path: Path) -> None:
        # 완전히 떨어진 형제 앵커는 정상이다.
        p = _write(
            tmp_path,
            "sibling.py",
            [_m("P_START"), "x = 1", _m("P_END"), _m("Q_START"), "y = 2", _m("Q_END")],
        )
        assert validate_anchor_file(p) == []


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTMULTIPLICITY_END ===


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTMALFORMED_START ===
class TestMalformed:
    def test_half_marker_is_not_counted_as_a_pair(self, tmp_path: Path) -> None:
        # 앞쪽 등호가 빠진 반쪽 마커. 느슨한 findall 은 정상 쌍으로 셌다.
        half_start = "# ANCHOR: D_START " + "=" * 3
        p = _write(tmp_path, "half.py", [half_start, "x = 1", _m("D_END")])
        problems = validate_anchor_file(p)
        # START 로 인정되지 않으므로 END 가 고아로 잡혀야 한다.
        assert any("D_END" in x for x in problems), problems

    def test_malformed_marker_is_surfaced(self, tmp_path: Path) -> None:
        # 정본도 legacy 도 아닌 "쓰다 만" 마커는 조용히 무시되면 안 된다.
        text = "# " + "=" * 3 + " ANCHOR: E_START\nx = 1\n"
        assert find_malformed_anchor_markers(text)

    def test_trailing_text_after_marker_is_surfaced(self, tmp_path: Path) -> None:
        text = f"# {MARKER.format(name='F_START')} 설명이 붙었다\n"
        assert find_malformed_anchor_markers(text)

    def test_block_comment_marker_is_surfaced(self, tmp_path: Path) -> None:
        text = f"/* {MARKER.format(name='G_START')} */\n"
        assert find_malformed_anchor_markers(text)

    def test_jsx_wrapped_marker_is_surfaced(self) -> None:
        # 생성기는 이 형태를 만들지 않으므로 정본 파서가 읽지 않는다.
        # 조용히 무시하면 그 파일은 보호받는 줄 알고 방치된다.
        text = "{/* " + MARKER.format(name="J_START") + " */}\n"
        assert find_malformed_anchor_markers(text)

    def test_marker_without_direction_suffix_is_surfaced(self) -> None:
        # `=== ANCHOR: FOO ===` — 형식은 정본인데 _START/_END 가 없다.
        text = "# " + MARKER.format(name="NODIR") + "\n"
        problems = find_malformed_anchor_markers(text)
        assert problems and "NODIR" in problems[0]

    def test_canonical_marker_is_not_malformed(self, tmp_path: Path) -> None:
        text = f"# {MARKER.format(name='H_START')}\nx = 1\n# {MARKER.format(name='H_END')}\n"
        assert find_malformed_anchor_markers(text) == []

    def test_prose_mentioning_anchor_is_not_malformed(self) -> None:
        # 주석 속 산문·경로 설명까지 잡으면 리포 자기 소스가 빨개진다.
        text = (
            "# format: /abs/path/file.py NUL # " + "=" * 3 + " ANCHOR: FOO_START ===\n"
            "# 앵커 경계(ANCHOR: NAME_START ~ NAME_END)를 지키세요\n"
        )
        assert find_malformed_anchor_markers(text) == []


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTMALFORMED_END ===


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTHASANCHORMARKERS_START ===
class TestHasAnchorMarkers:
    """'앵커가 있는가' 판정을 정본 파서 한 곳으로 모은다."""

    def test_string_literal_does_not_count(self) -> None:
        assert not has_anchor_markers(f's = "# {MARKER.format(name="X_START")}"')

    def test_legacy_does_not_count(self) -> None:
        assert not has_anchor_markers("# ANCHOR: X_START\n")

    def test_canonical_counts(self) -> None:
        assert has_anchor_markers(f"# {MARKER.format(name='X_START')}\n")


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTHASANCHORMARKERS_END ===
# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_END ===
