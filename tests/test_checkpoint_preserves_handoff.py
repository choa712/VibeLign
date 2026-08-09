"""vib checkpoint 가 PROJECT_CONTEXT.md 의 Session Handoff 블록을 보존하는지 검증.

handoff 는 세션 상태라 체크포인트가 재생성할 대상이 아니다. 예전에는
"덮어써집니다" 경고만 출력하고 블록 203줄을 그대로 날렸다.

블록의 끝은 전용 sentinel 로 표시한다. 서식(다음 H1)에서 추론하면
handoff 필드가 자유 텍스트라 양쪽으로 다 깨진다 — 첫 매치는 본문에 섞인
H1 에서 잘리고, 마지막 매치는 생성 본문을 handoff 로 흡수한다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.commands import vib_checkpoint_cmd
from vibelign.commands.vib_transfer_cmd import (
    HANDOFF_END_SENTINEL,
    _build_context_content,
    contains_handoff,
    extract_handoff_section,
)

HANDOFF = f"""## Session Handoff
> 이 블록은 세션 고유 정보입니다.

Generated: 2026-06-26 17:44

- **Primary work item**: out/report.html
- **Next action**: 튜토리얼 저장 구간 검증

### Active intent
지금 하던 일을 이어서.

---

{HANDOFF_END_SENTINEL}

"""

BODY = "# ⚡ demo — AI Transfer Context\n\n> 자동 생성됨\n"
CONTEXT = "<!--\n  ⚡ AI Transfer Context\n-->\n\n" + HANDOFF + BODY


class _Summary:
    file_count = 1
    pruned_count = 0
    pruned_bytes = 0


def _run_checkpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(vib_checkpoint_cmd, "resolve_project_root", lambda _: tmp_path)
    monkeypatch.setattr(
        vib_checkpoint_cmd, "create_for_cli", lambda root, msg: (_Summary(), None)
    )
    vib_checkpoint_cmd.run_vib_checkpoint(
        type("Args", (), {"json": False, "message": ["테스트"]})()
    )


# --- 추출 경계 ---------------------------------------------------------


def test_extract_ends_at_sentinel() -> None:
    section = extract_handoff_section(CONTEXT)
    assert section is not None
    assert section.startswith("## Session Handoff")
    assert "### Active intent" in section
    assert section.rstrip().endswith(HANDOFF_END_SENTINEL)
    assert "# ⚡ demo" not in section
    assert "자동 생성됨" not in section


def test_embedded_h1_in_handoff_text_does_not_truncate() -> None:
    """handoff 자유 텍스트가 어떤 H1 을 품어도 잘리지 않는다."""
    text = (
        "## Session Handoff\n"
        "- **Next action**: 커밋 메시지에 이런 줄이 있었다:\n"
        "# Embedded heading in free text\n"
        "# ⚡ demo — AI Transfer Context\n\n"
        "### Active intent\n"
        "이 줄이 살아남아야 한다.\n\n"
        f"{HANDOFF_END_SENTINEL}\n\n" + BODY
    )
    section = extract_handoff_section(text)
    assert section is not None
    assert "# Embedded heading in free text" in section
    assert "이 줄이 살아남아야 한다" in section
    assert "자동 생성됨" not in section


def test_generated_body_is_not_absorbed() -> None:
    """생성 본문(AGENTS.md 인용 등)에 H1 이 더 있어도 흡수되면 안 된다."""
    text = (
        "## Session Handoff\n"
        "- **Next action**: 작업 계속\n\n"
        f"{HANDOFF_END_SENTINEL}\n\n"
        + BODY
        + "\n# ⚡ other — AI Transfer Context\n\nAGENTS.md 인용 구간\n"
    )
    section = extract_handoff_section(text)
    assert section is not None
    assert "AGENTS.md 인용 구간" not in section
    assert "자동 생성됨" not in section


def test_missing_sentinel_returns_none() -> None:
    """구버전·수동 편집 문서는 경계를 확정할 수 없다."""
    assert extract_handoff_section("## Session Handoff\n내용\n\n" + BODY) is None


def test_extract_returns_none_without_handoff() -> None:
    assert extract_handoff_section(BODY) is None


def test_extract_returns_none_on_empty() -> None:
    assert extract_handoff_section("") is None


def test_contains_handoff_distinguishes_absent_from_unmarked() -> None:
    unmarked = "## Session Handoff\n지켜져야 하는 상태\n\n" + BODY
    assert contains_handoff(unmarked) is True
    assert extract_handoff_section(unmarked) is None
    assert contains_handoff(BODY) is False


# --- 재생성 ------------------------------------------------------------


def test_generated_handoff_carries_the_sentinel(tmp_path: Path) -> None:
    rebuilt = _build_context_content(
        tmp_path, handoff_data={"session_summary": "새 세션"}
    )
    assert HANDOFF_END_SENTINEL in rebuilt
    assert extract_handoff_section(rebuilt) is not None


def test_rebuild_without_preserve_drops_handoff(tmp_path: Path) -> None:
    assert "## Session Handoff" not in _build_context_content(tmp_path)


def test_rebuild_with_preserve_keeps_handoff(tmp_path: Path) -> None:
    rebuilt = _build_context_content(
        tmp_path, preserved_handoff=extract_handoff_section(CONTEXT)
    )
    assert "### Active intent" in rebuilt
    assert "out/report.html" in rebuilt
    assert "AI Transfer Context" in rebuilt


def test_preserved_block_survives_repeated_rebuilds(tmp_path: Path) -> None:
    """반복 체크포인트에서 블록이 마모되거나 본문을 삼키면 안 된다."""
    current = CONTEXT
    for _ in range(3):
        current = _build_context_content(
            tmp_path, preserved_handoff=extract_handoff_section(current)
        )
    assert extract_handoff_section(current) == extract_handoff_section(CONTEXT)


def test_explicit_handoff_data_wins_over_preserved(tmp_path: Path) -> None:
    rebuilt = _build_context_content(
        tmp_path,
        handoff_data={"session_summary": "새 세션 요약"},
        preserved_handoff=extract_handoff_section(CONTEXT),
    )
    assert "out/report.html" not in rebuilt
    assert "튜토리얼 저장 구간" not in rebuilt


# --- checkpoint 통합 ---------------------------------------------------


def test_checkpoint_skips_rewrite_when_sentinel_missing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """끝 표시가 없으면 파일을 아예 건드리지 않아야 한다 (영구 삭제 방지)."""
    ctx = tmp_path / "PROJECT_CONTEXT.md"
    ctx.write_text("## Session Handoff\n지켜져야 하는 상태\n\n" + BODY, encoding="utf-8")
    before = ctx.read_text(encoding="utf-8")

    _run_checkpoint(tmp_path, monkeypatch)

    assert ctx.read_text(encoding="utf-8") == before
    assert "끝 표시가 없어" in capsys.readouterr().out


def test_checkpoint_preserves_when_sentinel_present(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ctx = tmp_path / "PROJECT_CONTEXT.md"
    ctx.write_text(CONTEXT, encoding="utf-8")

    _run_checkpoint(tmp_path, monkeypatch)

    after = ctx.read_text(encoding="utf-8")
    assert extract_handoff_section(after) == extract_handoff_section(CONTEXT)
    assert "끝 표시가 없어" not in capsys.readouterr().out


def test_repeated_checkpoints_do_not_grow_the_block(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """체크포인트를 반복해도 handoff 가 생성 본문을 누적하지 않는다."""
    ctx = tmp_path / "PROJECT_CONTEXT.md"
    ctx.write_text(CONTEXT, encoding="utf-8")

    for _ in range(3):
        _run_checkpoint(tmp_path, monkeypatch)
        _ = capsys.readouterr()

    assert extract_handoff_section(ctx.read_text(encoding="utf-8")) == (
        extract_handoff_section(CONTEXT)
    )
