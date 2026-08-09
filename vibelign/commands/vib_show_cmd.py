# === ANCHOR: VIB_SHOW_CMD_START ===
"""vib show <file> <anchor>

지정한 파일에서 앵커 영역(`_START` ~ `_END` 사이)만 콘솔로 출력한다.
앵커 전체 파일을 읽지 않고 필요한 블록만 정밀 조회할 때 쓴다.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from vibelign.core.anchor_tools import extract_anchor_spans
from vibelign.core.project_root import resolve_project_root
from vibelign.terminal_render import cli_print

print = cli_print


def run_vib_show(args: Namespace) -> None:
    root = resolve_project_root(Path.cwd())
    rel: str = str(getattr(args, "file", "") or "").strip()
    anchor_name: str = str(getattr(args, "anchor", "") or "").strip()
    if not rel or not anchor_name:
        print("사용법: vib show <파일 경로> <앵커 이름>")
        return

    target = (root / rel).resolve()
    try:
        _ = target.relative_to(root.resolve())
    except ValueError:
        print(f"오류: {rel} 은 프로젝트 루트 밖에 있어요")
        return
    if not target.exists() or not target.is_file():
        print(f"오류: 파일을 찾을 수 없어요 — {rel}")
        return

    spans = extract_anchor_spans(target)
    if not spans:
        print(f"'{rel}' 에 앵커가 없어요")
        return

    # 정확 일치를 먼저 시도한다. 곧바로 정규화하면 이름 자체가 _END/_ 로 끝나는
    # 앵커(HEAD_EXCLUSIVE_END, __INIT__)를 영영 조회할 수 없다.
    requested = anchor_name.upper()
    matches = [s for s in spans if str(s.get("name", "")).upper() == requested]

    if not matches:
        # 마커 이름(FOO_START)으로 요청한 경우를 위한 폴백
        normalized = requested.rstrip("_")
        if normalized.endswith("_START") or normalized.endswith("_END"):
            normalized = normalized.rsplit("_", 1)[0]
        matches = [s for s in spans if str(s.get("name", "")).upper() == normalized]
    if not matches:
        available = ", ".join(sorted({str(s.get("name", "")) for s in spans}))
        print(f"앵커 '{anchor_name}' 를 '{rel}' 에서 찾을 수 없어요")
        if available:
            print(f"사용 가능한 앵커: {available}")
        return

    span = matches[0]
    start_val = span.get("start")
    end_val = span.get("end")
    if not isinstance(start_val, int):
        print("오류: 앵커 시작 줄을 파악할 수 없어요")
        return

    try:
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as e:
        print(f"오류: 파일을 읽을 수 없어요 — {e}")
        return

    end_line = end_val if isinstance(end_val, int) else len(lines)
    start_idx = max(0, start_val - 1)
    end_idx = min(len(lines), end_line)

    resolved_name = str(span.get("name", "")) or anchor_name
    header = f"{rel}:{start_val}-{end_line}  (앵커: {resolved_name})"
    print(header)
    print("-" * len(header))
    width = len(str(end_line))
    for offset, line in enumerate(lines[start_idx:end_idx]):
        line_no = start_val + offset
        print(f"{line_no:>{width}}  {line}")


# === ANCHOR: VIB_SHOW_CMD_END ===
