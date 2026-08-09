# === ANCHOR: VIB_SCAN_CMD_START ===
import importlib
from argparse import Namespace
from pathlib import Path
from typing import Callable, cast

from vibelign.core.meta_paths import MetaPaths
from vibelign.core.project_root import resolve_project_root
from vibelign.terminal_render import (
    clack_info,
    clack_intro,
    clack_outro,
    clack_step,
    clack_success,
    clack_warn,
)


def _write_project_map(root: Path, meta: MetaPaths) -> dict[str, object]:
    import json

    build_project_map = cast(
        Callable[[Path], dict[str, object]],
        getattr(
            importlib.import_module("vibelign.commands.vib_start_cmd"),
            "_build_project_map",
        ),
    )

    project_map = build_project_map(root)
    _ = meta.project_map_path.write_text(
        json.dumps(project_map, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return project_map


def run_vib_scan(args: Namespace) -> None:
    """앵커 스캔 + 코드맵 생성 + 앵커 인덱스 갱신을 한 번에 수행."""
    import json
    import types
    from vibelign.commands.vib_anchor_cmd import run_vib_anchor

    root = resolve_project_root(Path.cwd())
    meta = MetaPaths(root)

    clack_intro("VibeLign 스캔")

    # [1] 앵커 자동 삽입 (--auto 플래그 없으면 suggest만)
    clack_step("앵커 스캔 중...")
    anchor_args = types.SimpleNamespace(
        suggest=not getattr(args, "auto", False),
        auto=getattr(args, "auto", False),
        validate=False,
        dry_run=False,
        json=False,
        only_ext="",
        set_intent=None,
        intent="",
        auto_intent=False,
        list_intent=False,
    )
    run_vib_anchor(anchor_args)

    # [2] 앵커 무결성 검사 (+ --auto 시 자동 수정)
    clack_step("앵커 무결성 검사 중...")
    from vibelign.core.anchor_tools import (
        insert_module_anchors,
        strip_unreadable_markers,
        validate_anchor_file,
    )
    from vibelign.core.project_scan import iter_source_files, safe_read_text
    from vibelign.core.structure_policy import has_anchor_markers

    problems: list[str] = []
    problem_paths: list[Path] = []
    for path in iter_source_files(root):
        file_problems = [
            p for p in validate_anchor_file(path) if p != "앵커가 없습니다"
        ]
        if file_problems:
            rel = str(path.relative_to(root))
            for p in file_problems:
                problems.append(f"{rel}: {p}")
            problem_paths.append(path)
    if problems:
        clack_warn(f"앵커 문제 {len(problems)}건 발견:")
        for p in problems:
            clack_warn(f"  {p}")
        if getattr(args, "auto", False) and problem_paths:
            clack_step("읽히지 않는 마커 정리 중...")
            fixed: list[str] = []
            for p in problem_paths:
                # 읽히지 않는 줄(구 형식·훼손)만 걷어낸다. 예전엔 여기서
                # strip_anchors + 재삽입으로 파일의 **모든** 앵커를 갈아끼웠다.
                # 그러면 구 형식 마커 하나 때문에 사용자가 붙여둔
                # DATA_START/DATA_END 같은 이름과 메타데이터가 통째로 사라진다.
                # 짝이 안 맞는 정본 마커는 이름 자체가 정보이므로 지우지 않고
                # 보고만 한다 — 사람이 고칠 문제다.
                changed = strip_unreadable_markers(p)
                if not has_anchor_markers(safe_read_text(p)):
                    changed = insert_module_anchors(p) or changed
                if changed:
                    fixed.append(str(p.relative_to(root)))
            if fixed:
                clack_success(f"마커 정리 완료: {', '.join(fixed)}")
            else:
                clack_info(
                    "자동으로 고칠 수 있는 마커가 없습니다 — "
                    "짝이 맞지 않는 앵커는 이름이 정보라 직접 고쳐주세요."
                )
        else:
            clack_info(
                "vib anchor --validate 로 상세 확인, 또는 vib scan --auto 로 자동 수정하세요"
            )
    else:
        clack_success("앵커 무결성 이상 없음")

    # [3] 코드맵 재생성 — 앵커 수정 후 최신 상태 반영
    clack_step("코드맵 재생성 중...")
    if meta.project_map_path.exists():
        meta.ensure_vibelign_dir()
        project_map = _write_project_map(root, meta)
        # anchor_index.json도 코드맵 데이터에서 추출해 저장 (중복 스캔 없음)
        anchor_index = cast(dict[str, list[str]], project_map.get("anchor_index", {}))
        _ = meta.anchor_index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "anchors": anchor_index,
                    "files": {k: {"anchors": v} for k, v in anchor_index.items()},
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        meta.analysis_cache_path.unlink(missing_ok=True)
        clack_success(
            f"코드맵 갱신 완료: {project_map['file_count']}개 파일, 앵커 {len(anchor_index)}개 파일 포함"
        )
    else:
        clack_info("project_map.json 없음 — vib init 또는 vib start를 먼저 실행하세요")

    clack_outro(
        "스캔 완료. AI에게 project_map.json을 제공하면 전체 구조를 한 번에 파악해요."
    )


# === ANCHOR: VIB_SCAN_CMD_END ===
