# === ANCHOR: TEST_AUTO_REPAIR_PRESERVES_ANCHORS_START ===
"""자동 수리가 멀쩡한 앵커를 지우면 안 된다 (적대 리뷰 HIGH).

검증 항목을 늘리자(#3·#5) `vib scan --auto` 의 삭제 경로에 들어오는 파일이
넓어졌다. 예전 수리는 문제 파일의 **모든** 앵커를 지우고 일반 모듈 앵커로
갈아끼웠으므로, 구 형식 마커 하나 때문에 사용자가 붙여둔 이름과 그
메타데이터가 통째로 사라진다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import strip_anchors, strip_unreadable_markers
from vibelign.core.structure_policy import has_anchor_markers

MARKER = "=" * 3 + " ANCHOR: {name} " + "=" * 3


def _m(name: str) -> str:
    return "# " + MARKER.format(name=name)


def _write(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "mod.py"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# === ANCHOR: TEST_AUTO_REPAIR_PRESERVES_ANCHORS_TESTSURGICALREPAIR_START ===
class TestSurgicalRepair:
    def _mixed(self, tmp_path: Path) -> Path:
        return _write(
            tmp_path,
            [
                _m("DATA_START"),
                "DATA = 1",
                _m("DATA_END"),
                "# ANCHOR: STALE_START",  # 구 형식 — 어떤 파서도 안 읽는다
                "keep = 2",
            ],
        )

    def test_custom_anchor_names_survive(self, tmp_path: Path) -> None:
        p = self._mixed(tmp_path)
        assert strip_unreadable_markers(p) is True
        after = p.read_text(encoding="utf-8")
        assert "DATA_START" in after
        assert "DATA_END" in after

    def test_unreadable_marker_is_removed(self, tmp_path: Path) -> None:
        p = self._mixed(tmp_path)
        _ = strip_unreadable_markers(p)
        assert "STALE_START" not in p.read_text(encoding="utf-8")

    def test_code_survives(self, tmp_path: Path) -> None:
        p = self._mixed(tmp_path)
        _ = strip_unreadable_markers(p)
        after = p.read_text(encoding="utf-8")
        assert "DATA = 1" in after
        assert "keep = 2" in after

    def test_blunt_repair_would_have_destroyed_them(self, tmp_path: Path) -> None:
        """예전 수리와 대조 — 이 차이가 이 테스트의 존재 이유다."""
        p = self._mixed(tmp_path)
        _ = strip_anchors(p)
        assert "DATA_START" not in p.read_text(encoding="utf-8")

    def test_no_change_when_all_markers_are_canonical(self, tmp_path: Path) -> None:
        p = _write(tmp_path, [_m("OK_START"), "x = 1", _m("OK_END")])
        assert strip_unreadable_markers(p) is False
        assert has_anchor_markers(p.read_text(encoding="utf-8"))

    def test_string_literal_is_not_touched(self, tmp_path: Path) -> None:
        literal = 'SAMPLE = "' + _m("FOO_START") + '"'
        p = _write(tmp_path, [_m("M_START"), literal, _m("M_END"), "# ANCHOR: OLD_END"])
        _ = strip_unreadable_markers(p)
        assert literal in p.read_text(encoding="utf-8")


# === ANCHOR: TEST_AUTO_REPAIR_PRESERVES_ANCHORS_TESTSURGICALREPAIR_END ===
# === ANCHOR: TEST_AUTO_REPAIR_PRESERVES_ANCHORS_END ===
