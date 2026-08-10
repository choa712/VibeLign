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

    def test_commit_archives_before_replacing_handoff_json(self, tmp_path: Path) -> None:
        """보관이 handoff.json 교체보다 먼저여야 한다.

        순서가 뒤집히면 handoff.json 이 생겨 보관 조건이 막히고, 약속한
        보관 파일 없이 구버전 handoff 가 사라진다. 소스 순서가 아니라
        결과로 확인한다 — 구조가 바뀌어도 계약은 남는다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        original = "## Session Handoff\n구버전 인수인계\n"
        _ = ctx.write_text(original, encoding="utf-8")
        assert not MetaPaths(tmp_path).handoff_path.exists()

        archive, _content = commit_project_context(
            tmp_path,
            ctx,
            lambda: "새 본문",
            handoff_data=_handoff(),  # type: ignore[arg-type]
        )
        assert archive is not None
        assert archive.read_text(encoding="utf-8") == original

    def test_empty_handoff_json_does_not_suppress_archive(self, tmp_path: Path) -> None:
        """빈 객체는 'handoff 가 있다'로 치면 안 된다.

        렌더링되는 블록은 없는데 보관만 건너뛰어, 파일 안에만 있던 유일한
        인수인계가 그대로 덮인다.
        """
        stored = MetaPaths(tmp_path).handoff_path
        stored.parent.mkdir(parents=True, exist_ok=True)
        _ = stored.write_text("{}", encoding="utf-8")
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        body = "## Session Handoff\n살아있는 인수인계\n"
        _ = ctx.write_text(body, encoding="utf-8")

        assert load_handoff_data(tmp_path) is None
        archive = _archive_legacy_inline_handoff(tmp_path, ctx)
        assert archive is not None
        assert archive.read_text(encoding="utf-8") == body


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
        archive, content = commit_project_context(tmp_path, ctx, lambda: "생성물")
        assert archive is None
        assert content == "생성물"
        assert ctx.read_text(encoding="utf-8") == "생성물"

    def test_commit_writes_handoff_and_context_together(self, tmp_path: Path) -> None:
        """둘을 따로 쓰면 동시 실행 시 서로 다른 세션을 가리키게 된다."""
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = commit_project_context(
            tmp_path,
            ctx,
            lambda: "본문",
            handoff_data=_handoff(),  # type: ignore[arg-type]
        )
        assert ctx.read_text(encoding="utf-8") == "본문"
        stored = load_handoff_data(tmp_path)
        assert stored is not None and stored["source"] == "cli"

    def test_no_partial_state_is_visible_while_building(self, tmp_path: Path) -> None:
        """본문 생성 중에는 어느 파일도 아직 바뀌어 있으면 안 된다.

        handoff.json 을 먼저 갈아끼운 뒤 본문 생성이나 쓰기가 실패하면
        두 파일이 영구히 다른 세션을 가리킨다. 준비를 다 끝낸 뒤 교체만
        연달아 하는 구조인지 확인한다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = ctx.write_text("옛 본문", encoding="utf-8")
        save_handoff_data(tmp_path, _handoff(source="old"))  # type: ignore[arg-type]
        seen: list[str] = []

        def build() -> str:
            stored = load_handoff_data(tmp_path)
            seen.append(str(stored["source"]) if stored else "none")
            seen.append(ctx.read_text(encoding="utf-8"))
            return "새 본문"

        _ = commit_project_context(
            tmp_path,
            ctx,
            build,
            handoff_data=_handoff(source="new"),  # type: ignore[arg-type]
        )
        # 생성 시점엔 둘 다 옛 상태
        assert seen == ["old", "옛 본문"]
        # 끝난 뒤엔 둘 다 새 상태
        stored = load_handoff_data(tmp_path)
        assert stored is not None and stored["source"] == "new"
        assert ctx.read_text(encoding="utf-8") == "새 본문"

    def test_build_failure_leaves_both_files_untouched(self, tmp_path: Path) -> None:
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        _ = ctx.write_text("옛 본문", encoding="utf-8")
        save_handoff_data(tmp_path, _handoff(source="old"))  # type: ignore[arg-type]

        def boom() -> str:
            raise RuntimeError("본문 생성 실패")

        with pytest.raises(RuntimeError):
            _ = commit_project_context(
                tmp_path,
                ctx,
                boom,
                handoff_data=_handoff(source="new"),  # type: ignore[arg-type]
            )
        stored = load_handoff_data(tmp_path)
        assert stored is not None and stored["source"] == "old"
        assert ctx.read_text(encoding="utf-8") == "옛 본문"

    def test_unreadable_context_aborts_instead_of_overwriting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """읽을 수 없으면 '없다'가 아니라 '모른다' — 덮지 않고 멈춘다.

        파일은 못 읽어도 상위 디렉터리 권한만 있으면 교체는 되기 때문에,
        조용히 넘기면 유일한 handoff 가 보관 없이 사라진다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        original = "## Session Handoff\n유일한 인수인계\n"
        _ = ctx.write_text(original, encoding="utf-8")

        real_read = Path.read_text

        def refuse(self: Path, *args: object, **kwargs: object) -> str:
            if self == ctx:
                raise OSError("permission denied")
            return real_read(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", refuse)
        with pytest.raises(OSError):
            _ = commit_project_context(tmp_path, ctx, lambda: "새 본문")

        monkeypatch.undo()
        assert ctx.read_text(encoding="utf-8") == original

    def test_existing_file_mode_is_preserved(self, tmp_path: Path) -> None:
        """0600 으로 떨어뜨리면 팀 공유 체크아웃에서 남이 못 읽는다."""
        import os
        import stat

        p = tmp_path / "ctx.md"
        _ = p.write_text("x", encoding="utf-8")
        os.chmod(p, 0o644)
        atomic_write_text(p, "y")
        assert stat.S_IMODE(p.stat().st_mode) == 0o644

    def test_new_file_respects_umask(self, tmp_path: Path) -> None:
        """신규 파일 권한을 고정하면 umask 077 환경에서 내용이 노출된다.

        커널이 umask 를 적용하도록 맡겨, open()/write_text 와 같은 권한을 낸다.
        """
        import os
        import stat

        previous = os.umask(0o077)
        try:
            p = tmp_path / "restricted.md"
            atomic_write_text(p, "z")
            assert stat.S_IMODE(p.stat().st_mode) == 0o600
        finally:
            _ = os.umask(previous)

        previous = os.umask(0o022)
        try:
            q = tmp_path / "normal.md"
            atomic_write_text(q, "z")
            assert stat.S_IMODE(q.stat().st_mode) == 0o644
        finally:
            _ = os.umask(previous)

    def test_source_of_truth_is_replaced_before_derived(self, tmp_path: Path) -> None:
        """정본(handoff.json) 이 파생물(PROJECT_CONTEXT.md) 보다 먼저 교체돼야 한다.

        중간에 끊겼을 때 정본만 새것이면 다음 재생성이 본문을 다시 만들어
        복구되지만, 반대면 새 본문이 옛 handoff 로 되돌려져 손실이 된다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        order: list[str] = []
        real_replace = atomic_write_mod.os.replace

        def track(src: object, dst: object) -> None:
            order.append(Path(str(dst)).name)
            real_replace(src, dst)  # type: ignore[arg-type]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(atomic_write_mod.os, "replace", track)
            _ = commit_project_context(
                tmp_path,
                ctx,
                lambda: "본문",
                handoff_data=_handoff(),  # type: ignore[arg-type]
            )
        assert order == ["handoff.json", "PROJECT_CONTEXT.md"]

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

    def test_contended_lock_aborts_instead_of_interleaving(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """경합으로 잠금을 못 얻으면 진행하지 않는다.

        그대로 쓰면 두 세션의 handoff.json 과 PROJECT_CONTEXT.md 가 섞여
        새 AI 가 읽는 두 파일이 서로 다른 세션을 가리킨다.
        """
        monkeypatch.setattr(atomic_write_mod, "_lock_once", lambda _handle: False)
        with pytest.raises(TimeoutError):
            with file_lock(tmp_path / "busy.lock", timeout=0.1):
                raise AssertionError("본문이 실행되면 안 된다")

    def test_unsupported_locking_proceeds_but_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """잠금 미지원 환경에서는 막지 않되 조용히 넘기지도 않는다.

        막으면 그 환경에서 도구를 못 쓰고, 조용히 넘기면 사용자는 보호가
        걸려 있다고 믿는다.
        """
        monkeypatch.setattr(atomic_write_mod, "_lock_once", lambda _handle: None)
        monkeypatch.setattr(atomic_write_mod, "_warned_unserialized", False)
        with file_lock(tmp_path / "nofs.lock", timeout=0.1) as acquired:
            assert acquired is False
        assert "잠금 없이 진행" in capsys.readouterr().err

    def test_unserialized_warning_is_printed_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(atomic_write_mod, "_lock_once", lambda _handle: None)
        monkeypatch.setattr(atomic_write_mod, "_warned_unserialized", False)
        for _ in range(3):
            with file_lock(tmp_path / "nofs.lock", timeout=0.1):
                pass
        assert capsys.readouterr().err.count("잠금 없이 진행") == 1

    def test_partial_commit_is_reported_as_partial(self, tmp_path: Path) -> None:
        """첫 교체가 성공한 뒤 실패하면 '중단' 이라고 하면 안 된다.

        정본은 이미 갱신됐다. 아무것도 안 바뀐 실패와 같은 메시지를 내면
        사용자는 원래 상태가 그대로라고 믿고 다시 실행하지 않는다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        real_replace = atomic_write_mod.os.replace
        calls = {"n": 0}

        def fail_second(src: object, dst: object) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("두 번째 교체 실패")
            real_replace(src, dst)  # type: ignore[arg-type]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(atomic_write_mod.os, "replace", fail_second)
            with pytest.raises(atomic_write_mod.PartialCommitError) as caught:
                _ = commit_project_context(
                    tmp_path,
                    ctx,
                    lambda: "본문",
                    handoff_data=_handoff(),  # type: ignore[arg-type]
                )

        message = str(caught.value)
        assert "일부만 반영" in message
        assert "handoff.json" in message  # 갱신된 쪽
        assert "PROJECT_CONTEXT.md" in message  # 못 한 쪽
        # 정본이 먼저 갱신되므로 재실행으로 복구 가능한 방향이다
        assert load_handoff_data(tmp_path) is not None
        assert not ctx.exists()

    def test_symlink_inside_root_is_followed(self, tmp_path: Path) -> None:
        """링크를 일반 파일로 바꾸면 공유 정책(AGENTS.md 등)이 조용히 끊긴다.

        os.replace 는 링크 자체를 갈아끼운다. write_text 는 링크를 따라가므로
        root 안이면 그 동작에 맞춘다.
        """
        target = tmp_path / "shared.md"
        _ = target.write_text("원본", encoding="utf-8")
        link = tmp_path / "AGENTS.md"
        link.symlink_to(target)

        atomic_write_text(link, "새 내용", root=tmp_path)

        assert link.is_symlink()
        assert target.read_text(encoding="utf-8") == "새 내용"

    def test_broken_symlink_inside_root_creates_the_target(self, tmp_path: Path) -> None:
        link = tmp_path / "dangling.md"
        link.symlink_to(tmp_path / "missing.md")

        atomic_write_text(link, "생성", root=tmp_path)

        assert link.is_symlink()
        assert (tmp_path / "missing.md").read_text(encoding="utf-8") == "생성"

    def test_symlink_escaping_root_is_refused(self, tmp_path: Path) -> None:
        """프로젝트 밖을 가리키는 링크를 따라가면 임의 파일 쓰기가 된다.

        악의적 저장소가 .vibelign/handoff.json 을 시스템의 아무 파일로
        링크해 두면, 체크아웃 후 vib transfer --handoff 한 번으로 그 파일이
        덮인다. 조용히 링크만 바꾸지도 않는다 — 거부하고 알린다.
        """
        outside = tmp_path.parent / "victim.txt"
        _ = outside.write_text("건드리면 안 됨", encoding="utf-8")
        root = tmp_path / "proj"
        root.mkdir()
        link = root / "PROJECT_CONTEXT.md"
        link.symlink_to(outside)

        with pytest.raises(OSError, match="프로젝트 밖"):
            atomic_write_text(link, "탈취", root=root)

        assert outside.read_text(encoding="utf-8") == "건드리면 안 됨"

    def test_ancestor_symlink_escaping_root_is_refused(self, tmp_path: Path) -> None:
        """마지막 이름만 검사하면 상위 디렉터리 링크로 우회된다.

        `.vibelign` 자체를 바깥 디렉터리로 링크해 두면 `.vibelign/handoff.json`
        은 링크가 아니면서도 바깥에 쓰인다.
        """
        outside = tmp_path / "evil"
        outside.mkdir()
        victim = outside / "handoff.json"
        _ = victim.write_text("건드리면 안 됨", encoding="utf-8")
        root = tmp_path / "proj"
        root.mkdir()
        (root / ".vibelign").symlink_to(outside)

        target = root / ".vibelign" / "handoff.json"
        assert not target.is_symlink()  # 파일 자체는 링크가 아니다

        with pytest.raises(OSError, match="프로젝트 밖"):
            atomic_write_text(target, "탈취", root=root)

        assert victim.read_text(encoding="utf-8") == "건드리면 안 됨"

    def test_symlink_is_not_followed_without_root(self, tmp_path: Path) -> None:
        """기본값은 따라가지 않는 쪽 — root 를 아는 호출자만 허용한다."""
        target = tmp_path / "shared.md"
        _ = target.write_text("원본", encoding="utf-8")
        link = tmp_path / "link.md"
        link.symlink_to(target)

        atomic_write_text(link, "새 내용")

        assert not link.is_symlink()  # 링크 자체가 교체됨
        assert target.read_text(encoding="utf-8") == "원본"  # 대상은 그대로

    def test_commit_refuses_context_symlink_escaping_root(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "victim2.txt"
        _ = outside.write_text("보존", encoding="utf-8")
        root = tmp_path / "proj"
        root.mkdir()
        ctx = root / "PROJECT_CONTEXT.md"
        ctx.symlink_to(outside)

        with pytest.raises(OSError, match="프로젝트 밖"):
            _ = commit_project_context(root, ctx, lambda: "탈취")

        assert outside.read_text(encoding="utf-8") == "보존"

    def test_commit_pair_preserves_symlinks(self, tmp_path: Path) -> None:
        target = tmp_path / "real-context.md"
        _ = target.write_text("옛 본문", encoding="utf-8")
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        ctx.symlink_to(target)

        _ = commit_project_context(
            tmp_path,
            ctx,
            lambda: "새 본문",
            handoff_data=_handoff(),  # type: ignore[arg-type]
        )

        assert ctx.is_symlink()
        assert target.read_text(encoding="utf-8") == "새 본문"

    def test_after_commit_runs_only_when_files_landed(self, tmp_path: Path) -> None:
        """저장이 실패했는데 work_memory 에만 기록이 남으면 안 된다.

        기록은 파일이 실제로 착지한 뒤에 한다 — 앞에 두면 '저장 안 됨' 이라고
        보고하면서 메모리에는 그 handoff 가 남아 기록과 사실이 어긋난다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        ran: list[str] = []

        def boom() -> str:
            raise RuntimeError("본문 생성 실패")

        with pytest.raises(RuntimeError):
            _ = commit_project_context(
                tmp_path,
                ctx,
                boom,
                handoff_data=_handoff(),  # type: ignore[arg-type]
                after_commit=lambda: ran.append("recorded"),
            )
        assert ran == []

        _ = commit_project_context(
            tmp_path,
            ctx,
            lambda: "본문",
            handoff_data=_handoff(),  # type: ignore[arg-type]
            after_commit=lambda: ran.append("recorded"),
        )
        assert ran == ["recorded"]

    def test_staging_failure_leaves_no_temp_files(self, tmp_path: Path) -> None:
        """앞서 준비된 임시 파일을 남기면 안 된다.

        handoff 임시 파일에는 세션 내용이 그대로 들어 있어 그냥 쓰레기가 아니다.
        """
        ctx = tmp_path / "PROJECT_CONTEXT.md"
        real_stage = atomic_write_mod.stage_text
        calls = {"n": 0}

        def fail_second(path: Path, text: str, **kwargs: object) -> Path:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("두 번째 스테이징 실패")
            return real_stage(path, text, **kwargs)  # type: ignore[arg-type]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("vibelign.commands.vib_transfer_cmd.stage_text", fail_second)
            with pytest.raises(OSError):
                _ = commit_project_context(
                    tmp_path,
                    ctx,
                    lambda: "본문",
                    handoff_data=_handoff(),  # type: ignore[arg-type]
                )

        leftovers = [
            p.name
            for p in MetaPaths(tmp_path).vibelign_dir.iterdir()
            if p.name.endswith(".tmp")
        ]
        assert leftovers == []

    def test_escaping_vibelign_dir_is_refused_before_any_write(
        self, tmp_path: Path
    ) -> None:
        """경계 검사는 잠금·보관 파일을 만들기 전에 끝나야 한다.

        .vibelign 자체가 밖을 가리키면, 대상 경로를 검증할 즈음엔 이미
        project_context.lock 과 보관 파일이 바깥에 생겨 있다.
        """
        outside = tmp_path / "evil"
        outside.mkdir()
        root = tmp_path / "proj"
        root.mkdir()
        (root / ".vibelign").symlink_to(outside)
        ctx = root / "PROJECT_CONTEXT.md"
        _ = ctx.write_text("## Session Handoff\n기존\n", encoding="utf-8")

        with pytest.raises(OSError, match="프로젝트 밖"):
            _ = commit_project_context(root, ctx, lambda: "본문")

        assert list(outside.iterdir()) == []  # 잠금도 보관 파일도 안 생겼다

    def test_agents_failure_does_not_fail_the_save(self, tmp_path: Path) -> None:
        """저장이 끝난 뒤의 부수 작업 실패가 저장을 실패로 만들면 안 된다."""
        from vibelign.commands.vib_transfer_cmd import (
            _inject_agents_handoff_instruction,
        )

        outside = tmp_path.parent / "outside-agents.md"
        _ = outside.write_text("# 밖\n", encoding="utf-8")
        root = tmp_path / "proj"
        root.mkdir()
        (root / "AGENTS.md").symlink_to(outside)

        _inject_agents_handoff_instruction(root)  # 예외가 새어나오면 실패

        assert outside.read_text(encoding="utf-8") == "# 밖\n"

    def test_agents_md_symlink_is_followed(self, tmp_path: Path) -> None:
        """AGENTS.md 를 공유 정책 파일로 링크해 두는 설정이 흔하다."""
        from vibelign.commands.vib_transfer_cmd import (
            _inject_agents_handoff_instruction,
        )

        target = tmp_path / "shared-agents.md"
        _ = target.write_text("# 공유 정책\n", encoding="utf-8")
        link = tmp_path / "AGENTS.md"
        link.symlink_to(target)

        _inject_agents_handoff_instruction(tmp_path)

        assert link.is_symlink()
        assert "공유 정책" in target.read_text(encoding="utf-8")

    def test_partial_commit_error_is_an_oserror(self) -> None:
        # 기존 호출부의 except OSError 가 계속 받아야 한다.
        assert issubclass(atomic_write_mod.PartialCommitError, OSError)

    def test_timeout_error_is_an_oserror(self) -> None:
        # 호출부가 except OSError 로 받으므로 계층이 유지돼야 한다.
        assert issubclass(TimeoutError, OSError)

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
