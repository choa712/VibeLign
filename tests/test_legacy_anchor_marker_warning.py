"""구 형식 앵커 마커를 검증에서 드러내는지 확인.

정본 파서가 등호로 감싼 형식만 인정하도록 통일되면서, 구 형식만 쓰던
프로젝트는 업그레이드 후 조용히 보호 구역을 잃는다. 조용한 상실 대신
validate 에서 명시적으로 드러나야 한다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchors,
    find_legacy_anchor_markers,
    validate_anchor_file,
)

LEGACY_ONLY = (
    "// ANCHOR: LEGACY_ONE_START\n"
    "const a = 1;\n"
    "// ANCHOR: LEGACY_ONE_END\n"
)

MIXED = (
    "// === ANCHOR: CANONICAL_START ===\n"
    "const ok = 1;\n"
    "// ANCHOR: LEGACY_TWO_START\n"
    "const legacy = 2;\n"
    "// ANCHOR: LEGACY_TWO_END\n"
    "// === ANCHOR: CANONICAL_END ===\n"
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_finds_legacy_markers() -> None:
    problems = find_legacy_anchor_markers(LEGACY_ONLY)
    assert len(problems) == 1
    assert "구 형식" in problems[0]
    assert "LEGACY_ONE" in problems[0]


def test_no_warning_for_canonical_only() -> None:
    assert find_legacy_anchor_markers("// === ANCHOR: OK_START ===\n") == []


def test_inline_mention_is_not_a_legacy_marker() -> None:
    """주석 속 언급(줄 끝에 다른 내용이 붙은 경우)은 마커가 아니다."""
    assert find_legacy_anchor_markers("# 참고: ANCHOR: FOO_START 형식\n") == []


def test_validate_surfaces_legacy_only_file(tmp_path: Path) -> None:
    """구 형식만 있는 파일은 앵커 0개 + 구 형식 경고가 함께 나와야 한다."""
    p = _write(tmp_path, "legacy.ts", LEGACY_ONLY)
    assert extract_anchors(p) == []
    problems = validate_anchor_file(p)
    assert any("앵커가 없습니다" in x for x in problems)
    assert any("구 형식" in x for x in problems)


def test_validate_surfaces_legacy_in_mixed_file(tmp_path: Path) -> None:
    p = _write(tmp_path, "mixed.ts", MIXED)
    assert extract_anchors(p) == ["CANONICAL"]
    problems = validate_anchor_file(p)
    # 정본 앵커는 정상이라 짝 문제는 없고, 구 형식 경고만 있어야 한다
    assert [x for x in problems if "구 형식" in x]
    assert not [x for x in problems if "대응하는" in x]


def test_canonical_file_has_no_problems(tmp_path: Path) -> None:
    p = _write(tmp_path, "ok.ts", "// === ANCHOR: OK_START ===\nx\n// === ANCHOR: OK_END ===\n")
    assert validate_anchor_file(p) == []
