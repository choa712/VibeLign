"""리포 전수 앵커 정합 검사 (개발용).

세 추출기(spans/blocks/ranges)가 같은 이름 집합을 내놓는지, 인덱스가
광고하는 기본 이름을 전부 읽을 수 있는지 확인한다. PR #1 이 고친 결함
("광고는 됐는데 읽히지 않는 앵커 393개")의 회귀 감시용이다.

반드시 리포 루트에서 실행할 것 — 다른 디렉터리에서 돌리면 설치된
vibelign 패키지를 임포트해 엉뚱한 결과가 나온다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibelign.core.anchor_tools import (  # noqa: E402
    extract_anchor_blocks,
    extract_anchor_line_ranges,
    extract_anchor_spans,
    extract_anchors,
)
from vibelign.core.structure_policy import (  # noqa: E402
    COMMON_IGNORED_DIRS,
    SOURCE_FILE_EXTENSIONS,
)

_OCCURRENCE = re.compile(r"^(.*)_(\d+)$")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    if not (root / "vibelign" / "core" / "anchor_tools.py").exists():
        print("리포 루트에서 실행하세요.")
        return 2

    files = lost = unexplained = mismatched = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_FILE_EXTENSIONS:
            continue
        if any(part in COMMON_IGNORED_DIRS for part in path.parts):
            continue
        names = set(extract_anchors(path))
        if not names:
            continue
        files += 1
        blocks = set(extract_anchor_blocks(path))
        ranges = set(extract_anchor_line_ranges(path))
        spans = {str(item["name"]) for item in extract_anchor_spans(path)}

        lost += len(names - blocks) + len(names - ranges)
        for extra in (blocks - names) | (ranges - names):
            match = _OCCURRENCE.match(extra)
            if not (match and match.group(1) in names):
                unexplained += 1
        if spans != blocks or spans != ranges:
            mismatched += 1

    print(f"앵커 보유 파일 {files}개")
    print(f"  인덱스 기본 이름 소실: {lost}")
    print(f"  설명 안 되는 잉여 키: {unexplained}")
    print(f"  spans/blocks/ranges 불일치 파일: {mismatched}")
    ok = lost == 0 and unexplained == 0 and mismatched == 0
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
