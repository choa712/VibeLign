# === ANCHOR: VIB_CHECKPOINT_CMD_START ===
import importlib
import json
from datetime import datetime
from pathlib import Path
from collections.abc import Sequence
from typing import Protocol, cast

from vibelign.core.checkpoint_engine.router import (
    create_checkpoint,
    list_checkpoints,
)
from vibelign.core.project_root import resolve_project_root


from vibelign.terminal_render import cli_print

print = cli_print

class CheckpointLike(Protocol):
    checkpoint_id: str
    message: str
    created_at: str
    pinned: bool
    file_count: int
    pruned_count: int
    pruned_bytes: int


def _checkpoint_file_to_dict(file_item: object) -> dict[str, object] | None:
    path = getattr(file_item, "path", None)
    size_bytes = getattr(file_item, "size_bytes", None)
    if isinstance(file_item, dict):
        file_dict = cast(dict[str, object], file_item)
        path = file_dict.get("path") or file_dict.get("relative_path")
        size_bytes = file_dict.get("size_bytes", file_dict.get("size", 0))
    if not isinstance(path, str) or not path:
        return None
    return {
        "relative_path": path.replace("\\", "/"),
        "size": size_bytes if isinstance(size_bytes, int) else 0,
    }


class HandoffBoundaryUnresolved(Exception):
    """handoff 블록은 있는데 경계를 확정할 수 없는 상태.

    이때 PROJECT_CONTEXT.md 를 재생성하면 세션 상태가 영구 삭제된다.
    """


class HandoffExtractor(Protocol):
    def __call__(self, text: str) -> str | None: ...


class HandoffDetector(Protocol):
    def __call__(self, text: str) -> bool: ...


class TransferBuilder(Protocol):
    def __call__(
        self,
        root: Path,
        compact: bool = False,
        full: bool = False,
        handoff_data: dict[str, object] | None = None,
        preserved_handoff: str | None = None,
    ) -> str: ...


def _checkpoint_to_dict(cp: CheckpointLike) -> dict[str, object]:
    payload: dict[str, object] = {
        "checkpoint_id": cp.checkpoint_id,
        "message": cp.message,
        "created_at": cp.created_at,
        "pinned": cp.pinned,
        "file_count": getattr(cp, "file_count", None),
        "total_size_bytes": getattr(cp, "total_size_bytes", 0),
    }
    trigger = getattr(cp, "trigger", None)
    if trigger:
        payload["trigger"] = trigger
    git_commit_message = getattr(cp, "git_commit_message", None)
    if git_commit_message:
        payload["git_commit_message"] = git_commit_message
    checkpoint_files = cast(Sequence[object], getattr(cp, "files", []))
    files = [
        item
        for item in (
            _checkpoint_file_to_dict(file_item)
            for file_item in checkpoint_files
        )
        if item is not None
    ]
    payload["files"] = files
    return payload


def list_for_cli(root: Path) -> tuple[Sequence[CheckpointLike], str | None]:
    return list_checkpoints(root), None


def create_for_cli(root: Path, message: str) -> tuple[CheckpointLike | None, str | None]:
    return create_checkpoint(root, message), None


def _print_warning(warning: str | None, as_json: bool) -> None:
    if warning and not as_json:
        print(warning)


def run_vib_checkpoint(args: object) -> None:
    root = resolve_project_root(Path.cwd())
    as_json = bool(getattr(args, "json", False))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # `vib checkpoint list [--json]` 처리
    message_value = getattr(args, "message", [])
    message_parts = (
        cast(list[object], message_value) if isinstance(message_value, list) else []
    )
    first_part = message_parts[0] if message_parts else None
    if isinstance(first_part, str) and first_part.lower() == "list":
        checkpoints, warning = list_for_cli(root)
        if as_json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "warning": warning,
                        "checkpoints": [_checkpoint_to_dict(cp) for cp in checkpoints],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            _print_warning(warning, as_json)
            if not checkpoints:
                print("저장된 체크포인트가 없습니다.")
                return
            for i, cp in enumerate(checkpoints):
                marker = "  ◀ 최근" if i == 0 else ""
                pin = " [보호]" if cp.pinned else ""
                print(f"  [{i + 1:2}]  {cp.checkpoint_id}  {cp.message}{pin}{marker}")
        return

    # 메시지 처리 — input() 없이 동작
    if message_parts:
        user_msg = " ".join(str(part) for part in message_parts).strip()
    else:
        user_msg = ""

    if user_msg:
        msg = f"vibelign: checkpoint - {user_msg} ({timestamp})"
    else:
        msg = f"vibelign: checkpoint ({timestamp})"

    summary, warning = create_for_cli(root, msg)
    if summary is None:
        if as_json:
            print(
                json.dumps(
                    {"ok": False, "error": "no_changes", "warning": warning},
                    ensure_ascii=False,
                )
            )
        else:
            _print_warning(warning, as_json)
            print("변경된 파일이 없습니다. 체크포인트를 건너뜁니다.")
        return

    # PROJECT_CONTEXT.md 자동 갱신
    context_updated = False
    handoff_preserved = False
    context_update_error: str | None = None
    try:
        build_context_content = cast(
            TransferBuilder,
            getattr(
                cast(
                    object,
                    importlib.import_module("vibelign.commands.vib_transfer_cmd"),
                ),
                "_build_context_content",
            ),
        )
        extract_handoff_section = cast(
            HandoffExtractor,
            getattr(
                cast(
                    object,
                    importlib.import_module("vibelign.commands.vib_transfer_cmd"),
                ),
                "extract_handoff_section",
            ),
        )
        contains_handoff = cast(
            HandoffDetector,
            getattr(
                cast(
                    object,
                    importlib.import_module("vibelign.commands.vib_transfer_cmd"),
                ),
                "contains_handoff",
            ),
        )
        ctx_path = root / "PROJECT_CONTEXT.md"
        # handoff 는 세션 상태라 체크포인트가 재생성할 대상이 아니다.
        # 기존 블록을 떠서 그대로 실어 보존한다 (예전에는 경고만 하고 날렸다).
        preserved_handoff: str | None = None
        if ctx_path.exists():
            raw = ctx_path.read_text(encoding="utf-8")
            preserved_handoff = extract_handoff_section(raw)
            handoff_preserved = preserved_handoff is not None
            if preserved_handoff is None and contains_handoff(raw):
                # handoff 는 있는데 경계를 확정할 수 없다 (구버전·수동 편집 등).
                # 이 상태로 재생성하면 세션 상태가 영구 삭제되므로 손대지 않는다.
                raise HandoffBoundaryUnresolved(
                    "handoff 블록에 끝 표시가 없어 PROJECT_CONTEXT.md 를 그대로 둡니다"
                    " — `vib transfer --handoff` 로 한 번 다시 만들면 이후 자동 보존됩니다"
                )
        _ = ctx_path.write_text(
            build_context_content(root, preserved_handoff=preserved_handoff),
            encoding="utf-8",
        )
        context_updated = True
    except HandoffBoundaryUnresolved as exc:
        context_update_error = str(exc)
    except (ImportError, AttributeError, OSError) as exc:
        context_update_error = str(exc)

    if as_json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "warning": warning,
                    "message": user_msg or "(메시지 없음)",
                    "file_count": summary.file_count,
                    "pruned_count": summary.pruned_count,
                    "context_updated": context_updated,
                    "context_update_error": context_update_error,
                    "handoff_preserved": handoff_preserved,
                },
                ensure_ascii=False,
            )
        )
        return

    display_msg = user_msg if user_msg else "(메시지 없음)"
    _print_warning(warning, as_json)
    if context_update_error:
        _print_warning(f"PROJECT_CONTEXT.md 자동 갱신을 건너뜁니다: {context_update_error}", as_json)
    print("✓ 체크포인트 저장 완료!")
    print(f"  메시지: {display_msg}")
    print(f"  파일 수: {summary.file_count}개")
    if summary.pruned_count:
        freed_kb = max(1, round(summary.pruned_bytes / 1024))
        print(
            f"  오래된 체크포인트 {summary.pruned_count}개를 정리했고, 약 {freed_kb}KB를 비웠어요."
        )
    if handoff_preserved:
        print("  ↻ 기존 handoff 블록을 그대로 보존했습니다.")
        print("     최신 상태로 다시 만들려면 `vib transfer --handoff`를 실행하세요.")
    if context_updated:
        print("  📄 PROJECT_CONTEXT.md 자동 갱신 완료")
    print("문제가 생기면 `vib undo`로 되돌릴 수 있습니다.")


# === ANCHOR: VIB_CHECKPOINT_CMD_END ===
