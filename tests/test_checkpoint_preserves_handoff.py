"""vib checkpoint 가 PROJECT_CONTEXT.md 의 Session Handoff 블록을 보존하는지 검증.

handoff 는 세션 상태라 체크포인트가 재생성할 대상이 아니다. 예전에는
"덮어써집니다" 경고만 출력하고 블록 203줄을 그대로 날렸다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.commands.vib_transfer_cmd import (
    _build_context_content,
    extract_handoff_section,
)

HANDOFF = """## Session Handoff
> 이 블록은 세션 고유 정보입니다.

Generated: 2026-06-26 17:44

- **Primary work item**: `out/report.html`
- **Next action**: 튜토리얼 저장→되돌리기 구간 검증

### Active intent
지금 하던 일을 이어서.

---

"""

CONTEXT = (
    "<!--\n  ⚡ AI Transfer Context\n-->\n\n"
    + HANDOFF
    + "# ⚡ demo — AI Transfer Context\n\n> 자동 생성됨\n"
)


def test_extract_returns_block_up_to_first_h1() -> None:
    section = extract_handoff_section(CONTEXT)
    assert section is not None
    assert section.startswith("## Session Handoff")
    assert "### Active intent" in section
    assert "Primary work item" in section
    # H1 은 포함하지 않는다
    assert "# ⚡ demo" not in section


EMBEDDED_H1 = (
    "<!--\n  ⚡ AI Transfer Context\n-->\n\n"
    "## Session Handoff\n"
    "- **Next action**: 커밋 메시지에 이런 줄이 있었다:\n"
    "# Embedded heading in free text\n"
    "- **State references**: work_memory.json\n\n"
    "### Active intent\n"
    "마지막 세션 상태 — 이 줄이 살아남아야 한다.\n\n"
    "---\n\n"
    "# ⚡ demo — AI Transfer Context\n\n> 자동 생성됨\n"
)


def test_embedded_h1_in_handoff_text_does_not_truncate() -> None:
    """handoff 필드는 자유 텍스트라 '# ' 로 시작하는 줄을 품을 수 있다.

    그걸 경계로 삼으면 뒤쪽 세션 상태가 통째로 잘려 — 보존하려던 것을 잃는다.
    """
    section = extract_handoff_section(EMBEDDED_H1)
    assert section is not None
    assert "# Embedded heading in free text" in section
    assert "### Active intent" in section
    assert "이 줄이 살아남아야 한다" in section
    assert "# ⚡ demo" not in section


def test_handoff_text_mimicking_the_boundary_h1_does_not_truncate() -> None:
    """handoff 자유 텍스트가 경계 H1 모양을 그대로 품는 경우.

    커밋 메시지가 이 문서 자신을 인용하면 실제로 생길 수 있다.
    진짜 생성 H1 은 항상 뒤에 오므로 마지막 매치를 경계로 삼아야 한다.
    """
    mimic = (
        "## Session Handoff\n"
        "- **Next action**: 커밋 메시지가 이 문서를 인용했다:\n"
        "# ⚡ demo — AI Transfer Context\n"
        "- **State references**: work_memory.json\n\n"
        "### Active intent\n"
        "이 줄이 살아남아야 한다.\n\n"
        "---\n\n"
        "# ⚡ demo — AI Transfer Context\n\n> 자동 생성됨\n"
    )
    section = extract_handoff_section(mimic)
    assert section is not None
    assert "### Active intent" in section
    assert "이 줄이 살아남아야 한다" in section
    # 인용된 사본은 handoff 안에 남고, 진짜 생성 H1 은 잘려나간다
    assert section.count("# ⚡ demo — AI Transfer Context") == 1


def test_missing_boundary_h1_returns_none_instead_of_guessing() -> None:
    """경계를 확정할 수 없으면 어림짐작으로 자르지 않는다."""
    assert extract_handoff_section("## Session Handoff\n내용만 있고 H1 없음\n") is None


def test_extract_returns_none_without_handoff() -> None:
    assert extract_handoff_section("# ⚡ demo\n\n본문만 있음\n") is None


def test_extract_returns_none_on_empty() -> None:
    assert extract_handoff_section("") is None


def test_rebuild_without_preserve_drops_handoff(tmp_path: Path) -> None:
    """회귀 기준: preserved_handoff 를 안 넘기면 블록이 사라진다."""
    rebuilt = _build_context_content(tmp_path)
    assert "## Session Handoff" not in rebuilt


def test_rebuild_with_preserve_keeps_handoff(tmp_path: Path) -> None:
    preserved = extract_handoff_section(CONTEXT)
    rebuilt = _build_context_content(tmp_path, preserved_handoff=preserved)
    assert "## Session Handoff" in rebuilt
    assert "### Active intent" in rebuilt
    assert "Primary work item" in rebuilt
    # 재생성된 본문도 함께 있어야 한다
    assert "AI Transfer Context" in rebuilt


def test_preserved_block_survives_a_round_trip(tmp_path: Path) -> None:
    """보존 → 재추출 시 내용이 동일해야 한다 (반복 체크포인트에서 마모 방지)."""
    first = _build_context_content(
        tmp_path, preserved_handoff=extract_handoff_section(CONTEXT)
    )
    second = _build_context_content(
        tmp_path, preserved_handoff=extract_handoff_section(first)
    )
    assert extract_handoff_section(first) == extract_handoff_section(second)


def test_explicit_handoff_data_wins_over_preserved(tmp_path: Path) -> None:
    """--handoff 로 새로 만들 때는 새 블록이 우선한다."""
    rebuilt = _build_context_content(
        tmp_path,
        handoff_data={"session_summary": "새 세션 요약"},
        preserved_handoff=extract_handoff_section(CONTEXT),
    )
    # 보존 블록 고유 문자열이 남으면 안 된다
    # ("Primary work item" 은 새로 생성되는 블록도 쓰는 문구라 판별에 못 쓴다)
    assert "out/report.html" not in rebuilt
    assert "튜토리얼 저장→되돌리기" not in rebuilt
