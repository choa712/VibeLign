# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_START ===
"""validate 는 마커의 개수·중첩·형식 훼손을 실제로 잡아야 한다 (issue #5, #3).

기존 validator 는 이름의 집합 포함 여부만 봤다. 같은 이름의 START 2개 +
END 1개가 오류 없이 통과했는데, 추출은 안쪽 블록만 선택하므로 바깥 구간이
보호 없이 남는다. 검증이 통과했으니 사용자는 알 수 없다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    find_crossing_anchors,
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

    def test_crossing_anchors_are_blocked(self, tmp_path: Path) -> None:
        """교차는 중첩이 아니고, 이제 검증 실패다.

        P_START Q_START P_END Q_END 에서 블록 P 는 Q 의 여는 마커만 품는다.
        P 를 고치면 Q 의 경계가 깨진다.

        생성기가 이 형태를 스스로 만들어내던 동안에는 경고로만 뒀다 — 차단하면
        `vib anchor --auto` 를 돌린 모든 프로젝트가 깨졌다. 원인 3종을 고치고
        `vib anchor --repair` 로 기존 파일을 정리한 뒤에야 올렸다 (issue #7).
        """
        lines = [_m("P_START"), _m("Q_START"), "x = 1", _m("P_END"), _m("Q_END")]
        p = _write(tmp_path, "cross.py", lines)

        problems = validate_anchor_file(p)
        assert any("교차" in x for x in problems), problems

    def test_sequential_anchors_have_no_crossing(self, tmp_path: Path) -> None:
        lines = [_m("P_START"), "x = 1", _m("P_END"), _m("Q_START"), "y = 2", _m("Q_END")]
        p = _write(tmp_path, "sibling.py", lines)
        assert validate_anchor_file(p) == []
        assert find_crossing_anchors("\n".join(lines) + "\n") == []

    def test_unmatched_ends_scale_linearly(self) -> None:
        """짝 없는 END 가 많으면 예전 구현은 매번 열린 목록을 끝까지 훑었다.

        그 경로에선 교차가 안 잡혀 findings 상한도 안 걸리므로, 저장소 하나로
        vib scan 을 멈출 수 있었다.
        """
        import time

        def unmatched(n: int) -> str:
            lines = [_m(f"S{i}_START") for i in range(n)]
            lines += [_m(f"E{i}_END") for i in range(n)]
            return "\n".join(lines) + "\n"

        timings: dict[int, float] = {}
        for n in (1000, 2000):
            start = time.perf_counter()
            assert find_crossing_anchors(unmatched(n)) == []
            timings[n] = time.perf_counter() - start

        ratio = timings[2000] / max(timings[1000], 1e-6)
        assert ratio < 3.0, f"N 2배에 {ratio:.1f}배 — 2차 회귀 의심"

    def test_crossing_diagnostics_are_bounded(self) -> None:
        """겹친 앵커 수에 비례한 메시지가 그 수만큼 나오면 O(N^2) 이 된다.

        악성 소스 하나로 vib scan 이 메모리를 태울 수 있다 (8000 앵커 실측
        2.24억 자). 보여주는 상대 수와 findings 수 양쪽에 상한을 둔다.
        """
        n = 4000
        lines = [_m(f"A{i}_START") for i in range(n)]
        lines += [_m(f"A{i}_END") for i in range(n)]  # 전부 교차
        problems = find_crossing_anchors("\n".join(lines) + "\n")

        assert len(problems) <= 60, f"findings 상한 없음: {len(problems)}"
        total = sum(len(x) for x in problems)
        assert total < 100_000, f"진단 크기 폭발: {total:,}자"
        assert any("생략" in x for x in problems)

    def test_proper_nesting_has_no_crossing(self) -> None:
        text = "\n".join([_m("M_START"), _m("M_F_START"), "x", _m("M_F_END"), _m("M_END")])
        assert find_crossing_anchors(text) == []

    def test_validate_cli_fails_on_crossing(self, tmp_path: Path) -> None:
        """CLI 도 기본값에서 실패해야 한다 — 별도 플래그 없이."""
        import json
        import os
        import subprocess
        import sys

        lines = [_m("P_START"), _m("Q_START"), "x = 1", _m("P_END"), _m("Q_END")]
        (tmp_path / "src").mkdir()
        _ = (tmp_path / "src" / "mod.py").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, "-m", "vibelign", "anchor", "--validate", "--json"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert any("교차" in p for p in payload["data"]["problems"])


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
    """'앵커가 있는가' 판정을 정본 파서 한 곳으로 모은다.

    실제로 추출 가능한 블록이 하나라도 있어야 참이다. 이 판정이 헐거우면
    precheck·guard 는 통과시키는데 보호 구간은 0인 상태가 된다.
    """

    def _pair(self, name: str) -> str:
        return f"# {MARKER.format(name=name + '_START')}\nx = 1\n# {MARKER.format(name=name + '_END')}\n"

    def test_string_literal_does_not_count(self) -> None:
        assert not has_anchor_markers(f's = "# {MARKER.format(name="X_START")}"')

    def test_legacy_does_not_count(self) -> None:
        assert not has_anchor_markers("# ANCHOR: X_START\n# ANCHOR: X_END\n")

    def test_paired_canonical_counts(self) -> None:
        assert has_anchor_markers(self._pair("X"))

    def test_lone_start_does_not_count(self) -> None:
        assert not has_anchor_markers(f"# {MARKER.format(name='X_START')}\n")

    def test_lone_end_does_not_count(self) -> None:
        # END 만 있으면 추출되는 블록이 0이다 — 보호받는 척만 한다.
        assert not has_anchor_markers(f"# {MARKER.format(name='FAKE_END')}\n")

    def test_direction_less_marker_does_not_count(self) -> None:
        assert not has_anchor_markers(f"# {MARKER.format(name='NODIR')}\n")

    def test_mismatched_names_do_not_count(self) -> None:
        text = (
            f"# {MARKER.format(name='A_START')}\nx = 1\n# {MARKER.format(name='B_END')}\n"
        )
        assert not has_anchor_markers(text)


# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_TESTHASANCHORMARKERS_END ===
# === ANCHOR: TEST_ANCHOR_VALIDATE_PAIRING_END ===
