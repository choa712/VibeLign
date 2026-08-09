# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_START ===
"""handoff 는 PROJECT_CONTEXT.md 밖에 보관돼야 한다 (issue #6, #2).

생성 문서 안에 끼워 두면 재생성(=체크포인트)마다 경계를 다시 찾아야 하는데,
신뢰할 수 없는 자유 텍스트를 in-band 구분자로 감싸는 방식은 구분자가
무엇이든 위조된다. 경계 추론 3종이 모두 깨진 뒤 저장 구조를 바꿨다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibelign.core import atomic_write as atomic_write_mod
from vibelign.commands.vib_transfer_cmd import (
    _archive_legacy_inline_handoff,
    _build_context_content,
    load_handoff_data,
    save_handoff_data,
    commit_project_context,
)
from vibelign.core.atomic_write import atomic_write_text, file_lock
from vibelign.core.meta_paths import MetaPaths


def _handoff(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "generated_at": "2026-08-10 12:00:00",
        "source": "cli",
        "quality": "explicit",
        "active_intent": "앵커 파서 결함을 마저 고친다",
        "unfinished_work": "issue 2 원자적 쓰기",
        "verification": ["pytest 1523 passed"],
    }
    data.update(overrides)
    return data


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTROUNDTRIP_START ===
class TestRoundTrip:
    def test_saved_handoff_is_loaded_back(self, tmp_path: Path) -> None:
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        loaded = load_handoff_data(tmp_path)
        assert loaded is not None
        assert loaded["active_intent"] == "앵커 파서 결함을 마저 고친다"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_handoff_data(tmp_path) is None

    def test_corrupt_file_returns_none_instead_of_raising(self, tmp_path: Path) -> None:
        path = MetaPaths(tmp_path).handoff_path
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("{ not json", encoding="utf-8")
        assert load_handoff_data(tmp_path) is None

    def test_handoff_lives_outside_project_context(self, tmp_path: Path) -> None:
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        assert MetaPaths(tmp_path).handoff_path.exists()
        assert not (tmp_path / "PROJECT_CONTEXT.md").exists()


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTROUNDTRIP_END ===


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTREGENERATION_START ===
class TestRegeneration:
    """체크포인트가 부르는 무인자 재생성에서도 handoff 가 살아남아야 한다."""

    def test_context_rebuild_without_args_keeps_handoff(self, tmp_path: Path) -> None:
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        rebuilt = _build_context_content(tmp_path)
        assert "## Session Handoff" in rebuilt
        assert "앵커 파서 결함을 마저 고친다" in rebuilt

    def test_rebuild_without_stored_handoff_has_no_block(self, tmp_path: Path) -> None:
        rebuilt = _build_context_content(tmp_path)
        assert "## Session Handoff" not in rebuilt

    def test_free_text_containing_headings_survives(self, tmp_path: Path) -> None:
        # 경계 추론 시절 1차 실패: handoff 본문의 '# ' 줄에서 잘렸다.
        tricky = "커밋 메시지 인용:\n# fix(anchor): 경계\n다음 단계는 이것"
        save_handoff_data(tmp_path, _handoff(unfinished_work=tricky))  # type: ignore[arg-type]
        rebuilt = _build_context_content(tmp_path)
        assert "다음 단계는 이것" in rebuilt

    def test_free_text_containing_sentinel_survives(self, tmp_path: Path) -> None:
        # 3차 실패: 전용 sentinel 이 자유 텍스트에 들어가면 그 뒤를 잃었다.
        tricky = "sentinel 예시: <!-- vibelign:handoff-end --> 그 뒤에도 내용이 있다"
        save_handoff_data(tmp_path, _handoff(unfinished_work=tricky))  # type: ignore[arg-type]
        rebuilt = _build_context_content(tmp_path)
        assert "그 뒤에도 내용이 있다" in rebuilt

    def test_repeated_rebuild_does_not_accumulate(self, tmp_path: Path) -> None:
        # 2차 실패: 생성 본문을 handoff 로 흡수해 체크포인트마다 불어났다.
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        first = _build_context_content(tmp_path)
        for _ in range(3):
            latest = _build_context_content(tmp_path)
        assert latest.count("## Session Handoff") == 1
        assert abs(len(latest) - len(first)) < 200  # 타임스탬프 차이만


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTREGENERATION_END ===


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTLEGACYMIGRATION_START ===
class TestLegacyMigration:
    """구버전 파일 안의 handoff 는 추측해서 자르지 말고 통째로 보관한다."""

    def test_inline_handoff_is_archived_whole(self, tmp_path: Path) -> None:
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        body = "## Session Handoff\n중요한 내용\n---\n# 생성 본문\n"
        _ = ctx.write_text(body, encoding="utf-8")
        archive = _archive_legacy_inline_handoff(tmp_path, ctx)
        assert archive is not None
        assert archive.read_text(encoding="utf-8") == body

    def test_no_archive_when_handoff_json_exists(self, tmp_path: Path) -> None:
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = ctx.write_text("## Session Handoff\nx\n", encoding="utf-8")
        assert _archive_legacy_inline_handoff(tmp_path, ctx) is None

    def test_no_archive_when_no_inline_handoff(self, tmp_path: Path) -> None:
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = ctx.write_text("# 그냥 생성 본문\n", encoding="utf-8")
        assert _archive_legacy_inline_handoff(tmp_path, ctx) is None

    def test_corrupt_handoff_json_does_not_suppress_archive(
        self, tmp_path: Path
    ) -> None:
        """깨진 handoff.json 의 '존재'만으로 보관을 건너뛰면 안 된다.

        load 는 None 을 주므로 재생성물엔 블록이 없는데, 존재만 보고
        보관을 건너뛰면 아직 멀쩡한 파일 안의 handoff 가 그대로 덮인다.
        """
        stored = MetaPaths(tmp_path).handoff_path
        stored.parent.mkdir(parents=True, exist_ok=True)
        _ = stored.write_text("{ 깨진 json", encoding="utf-8")
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        body = "## Session Handoff\n아직 살아있는 인수인계\n"
        _ = ctx.write_text(body, encoding="utf-8")

        archive = _archive_legacy_inline_handoff(tmp_path, ctx)
        assert archive is not None
        assert archive.read_text(encoding="utf-8") == body

    def test_archive_runs_before_save_inside_commit(self) -> None:
        """보관이 저장보다 먼저 호출돼야 한다.

        순서가 뒤집히면 save 가 handoff.json 을 만들어 보관 조건이 막히고,
        약속한 보관 파일 없이 구버전 handoff 가 사라진다. 소스 순서로 고정한다.
        """
        sources = {
            "cli": (Path("vibelign") / "commands" / "vib_transfer_cmd.py"),
        }
        for label, path in sources.items():
            lines = path.read_text(encoding="utf-8").splitlines()
            # def 줄은 제외한다 — 정의가 위에 있다는 이유로 항상 통과하면
            # 이 테스트는 아무것도 검증하지 않는다.
            archive_lines = [
                i
                for i, x in enumerate(lines)
                if "_archive_legacy_inline_handoff(" in x
                and not x.lstrip().startswith("def ")
            ]
            save_lines = [
                i
                for i, x in enumerate(lines)
                if x.strip().startswith("save_handoff_data(")
            ]
            assert save_lines, f"{label}: save_handoff_data 호출이 없습니다"
            for save_at in save_lines:
                earlier = [i for i in archive_lines if i < save_at]
                assert earlier, (
                    f"{label}:{save_at + 1} save_handoff_data 앞에 "
                    "_archive_legacy_inline_handoff 호출이 없습니다"
                )


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTLEGACYMIGRATION_END ===


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTATOMICWRITE_START ===
class TestAtomicWrite:
    def test_replaces_content(self, tmp_path: Path) -> None:
        p = tmp_path / "out.md"
        atomic_write_text(p, "first")
        atomic_write_text(p, "second")
        assert p.read_text(encoding="utf-8") == "second"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        p = tmp_path / "deep" / "nested" / "out.md"
        atomic_write_text(p, "x")
        assert p.read_text(encoding="utf-8") == "x"

    def test_no_temp_files_left_behind(self, tmp_path: Path) -> None:
        p = tmp_path / "out.md"
        atomic_write_text(p, "x")
        assert [f.name for f in tmp_path.iterdir()] == ["out.md"]

    def test_original_survives_failed_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """교체 직전에 죽어도 원본이 남고 임시 파일이 치워져야 한다."""
        p = tmp_path / "out.md"
        atomic_write_text(p, "original")

        def boom(_src: object, _dst: object) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr(atomic_write_mod.os, "replace", boom)
        with pytest.raises(OSError):
            atomic_write_text(p, "new")

        assert p.read_text(encoding="utf-8") == "original"
        assert [f.name for f in tmp_path.iterdir()] == ["out.md"]

    def test_reader_never_sees_partial_content(self, tmp_path: Path) -> None:
        """쓰는 도중 읽어도 옛 내용 아니면 새 내용, 그 중간은 없다."""
        p = tmp_path / "out.md"
        atomic_write_text(p, "old" * 1000)
        seen: list[str] = []

        real_replace = atomic_write_mod.os.replace

        def replace_after_peek(src: object, dst: object) -> None:
            seen.append(p.read_text(encoding="utf-8"))
            real_replace(src, dst)  # type: ignore[arg-type]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(atomic_write_mod.os, "replace", replace_after_peek)
            atomic_write_text(p, "new" * 1000)

        # 교체 직전 시점에도 파일은 완전한 옛 내용이었다
        assert seen == ["old" * 1000]
        assert p.read_text(encoding="utf-8") == "new" * 1000

    def test_commit_project_context_uses_atomic_path(self, tmp_path: Path) -> None:
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        assert commit_project_context(tmp_path, ctx, "생성물") is None
        assert ctx.read_text(encoding="utf-8") == "생성물"

    def test_commit_writes_handoff_and_context_together(self, tmp_path: Path) -> None:
        """둘을 따로 쓰면 동시 실행 시 서로 다른 세션을 가리키게 된다."""
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = commit_project_context(
            tmp_path, ctx, "본문", handoff_data=_handoff()  # type: ignore[arg-type]
        )
        assert ctx.read_text(encoding="utf-8") == "본문"
        stored = load_handoff_data(tmp_path)
        assert stored is not None and stored["source"] == "cli"

    def test_lock_is_advisory_and_reentrant_across_calls(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "x.lock"
        with file_lock(lock_path) as first:
            assert first is True
        with file_lock(lock_path) as second:
            assert second is True

    def test_body_oserror_propagates_unchanged(self, tmp_path: Path) -> None:
        """with 본문의 OSError 가 원형 그대로 올라와야 한다.

        yield 를 try/except OSError 로 감싸면 본문 예외가 제너레이터로
        되돌아와 두 번째 yield 를 실행하고, 디스크 가득참 같은 진짜 원인이
        'generator didn't stop after throw()' 로 뒤바뀌어 사라진다.
        """
        with pytest.raises(OSError, match="disk full"):
            with file_lock(tmp_path / "y.lock"):
                raise OSError("disk full")

    def test_lock_released_after_body_error(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "z.lock"
        with pytest.raises(RuntimeError):
            with file_lock(lock_path):
                raise RuntimeError("boom")
        with file_lock(lock_path) as again:
            assert again is True

    def test_saved_handoff_json_is_valid(self, tmp_path: Path) -> None:
        save_handoff_data(tmp_path, _handoff())  # type: ignore[arg-type]
        raw = MetaPaths(tmp_path).handoff_path.read_text(encoding="utf-8")
        assert json.loads(raw)["source"] == "cli"


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTATOMICWRITE_END ===


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTWRITEPATHPARITY_START ===
class TestWritePathParity:
    """PROJECT_CONTEXT.md 를 쓰는 경로가 CLI·MCP 둘이라 갈라지기 쉽다.

    MCP 쪽만 save_handoff_data 를 빠뜨리면 'CLI 로 만든 handoff 는 남고
    MCP 로 만든 것만 사라지는' 재현하기 어려운 버그가 된다. 실제로 처음
    구현했을 때 그렇게 빠져 있었다.
    """

    def _source(self, name: str) -> str:
        return (
            Path("vibelign") / "mcp" / "mcp_transfer_handlers.py"
            if name == "mcp"
            else Path("vibelign") / "commands" / "vib_transfer_cmd.py"
        ).read_text(encoding="utf-8")

    def test_mcp_goes_through_the_same_commit_helper(self) -> None:
        source = self._source("mcp")
        assert "commit_project_context(" in source
        assert "ctx_path.write_text" not in source

    def test_cli_goes_through_the_same_commit_helper(self) -> None:
        assert "commit_project_context(" in self._source("cli")

    def test_no_raw_project_context_write_remains(self) -> None:
        for name in ("mcp", "cli"):
            source = self._source(name)
            assert "out_path.write_text(content" not in source
            assert "ctx_path.write_text(content" not in source


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTWRITEPATHPARITY_END ===


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTDRYRUNWRITESNOTHING_START ===
class TestDryRunWritesNothing:
    """dry-run 이 파일을 남기면 미리보기가 아니라 그냥 실행이다."""

    def _run(self, cwd: Path, *args: str) -> int:
        import os
        import subprocess
        import sys

        proc = subprocess.run(
            [sys.executable, "-m", "vibelign", "transfer", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        )
        return proc.returncode

    def _project(self, tmp_path: Path) -> Path:
        marker = "=" * 3
        (tmp_path / "src").mkdir()
        _ = (tmp_path / "src" / "app.py").write_text(
            f"# {marker} ANCHOR: APP_START {marker}\n"
            "x = 1\n"
            f"# {marker} ANCHOR: APP_END {marker}\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_dry_run_leaves_no_state_files(self, tmp_path: Path) -> None:
        root = self._project(tmp_path)
        original = "## Session Handoff\n구버전 인수인계\n"
        ctx = root / "PROJECT_CONTEXT.md"
        _ = ctx.write_text(original, encoding="utf-8")

        rc = self._run(
            root,
            "--handoff",
            "--no-prompt",
            "--dry-run",
            "--session-summary",
            "미리보기",
            "--first-next-action",
            "다음",
        )
        assert rc == 0
        meta = MetaPaths(root)
        assert not meta.handoff_path.exists()
        assert not meta.work_memory_path.exists()
        assert list(meta.vibelign_dir.glob("handoff-legacy-*.md")) == []
        assert ctx.read_text(encoding="utf-8") == original

    def test_ai_dry_run_does_not_take_the_writing_branch(self, tmp_path: Path) -> None:
        # --ai 비대화형 분기는 무조건 파일을 쓴다 — dry_run 이면 타면 안 된다.
        root = self._project(tmp_path)
        rc = self._run(
            root,
            "--handoff",
            "--ai",
            "--no-prompt",
            "--dry-run",
            "--session-summary",
            "미리보기",
            "--first-next-action",
            "다음",
        )
        assert rc == 0
        assert not (root / "PROJECT_CONTEXT.md").exists()
        assert not MetaPaths(root).handoff_path.exists()


# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_TESTDRYRUNWRITESNOTHING_END ===
# === ANCHOR: TEST_HANDOFF_OUT_OF_BAND_STORAGE_END ===
