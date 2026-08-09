"""중첩 앵커 블록 추출의 메모리 특성 회귀 테스트.

중첩 앵커는 바깥 블록이 안쪽 본문을 다시 담으므로, 모든 블록을 dict 로
만들면 중첩 깊이에 비례해 메모리가 늘어난다 (깊이 600→1200 에서 peak
10.3MB→41.3MB, 정확히 4배 = 2차). 모든 블록을 훑기만 하면 되는 호출자는
iter_anchor_blocks 로 한 번에 하나만 들고 있어야 한다.
"""

from __future__ import annotations

import tracemalloc
from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchor_blocks,
    extract_anchor_line_ranges,
    iter_anchor_blocks,
)


def _deeply_nested(tmp_path: Path, depth: int, name: str = "deep.py") -> Path:
    lines = [f"# === ANCHOR: A{i}_START ===" for i in range(depth)]
    lines.append("x = 1")
    lines += [f"# === ANCHOR: A{i}_END ===" for i in reversed(range(depth))]
    p = tmp_path / name
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _peak(fn) -> int:
    tracemalloc.start()
    try:
        fn()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_iter_matches_dict_extraction(tmp_path: Path) -> None:
    p = _deeply_nested(tmp_path, 40)
    assert dict(iter_anchor_blocks(p)) == extract_anchor_blocks(p)


def test_iter_peak_is_far_below_dict_peak(tmp_path: Path) -> None:
    p = _deeply_nested(tmp_path, 600)
    dict_peak = _peak(lambda: extract_anchor_blocks(p))
    iter_peak = _peak(lambda: [None for _ in iter_anchor_blocks(p)])
    # 실측 25배 차이. 환경 변동을 감안해 5배만 요구한다.
    assert iter_peak * 5 < dict_peak, (iter_peak, dict_peak)


def test_iter_peak_scales_linearly(tmp_path: Path) -> None:
    small = _deeply_nested(tmp_path, 600, "small.py")
    large = _deeply_nested(tmp_path, 1200, "large.py")
    small_peak = _peak(lambda: [None for _ in iter_anchor_blocks(small)])
    large_peak = _peak(lambda: [None for _ in iter_anchor_blocks(large)])
    # 입력 2배에 메모리 2배 근처여야 한다 (2차면 4배). 3배를 상한으로 둔다.
    assert large_peak < small_peak * 3, (small_peak, large_peak)


def _same_name_nested(tmp_path: Path, depth: int, name: str) -> Path:
    lines = ["# === ANCHOR: A_START ==="] * depth
    lines.append("x = 1")
    lines += ["# === ANCHOR: A_END ==="] * depth
    p = tmp_path / name
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def test_same_name_nesting_scales_linearly(tmp_path: Path) -> None:
    """동일 이름이 겹쳐 열리면 END 마다 join 이 돌아 2차 비용이 됐다.

    구간만 모으고 본문은 이름당 한 번만 만들면 선형이 된다.
    """
    import time

    def elapsed(p: Path) -> float:
        t0 = time.perf_counter()
        extract_anchor_blocks(p, only={"A"})
        return time.perf_counter() - t0

    small = elapsed(_same_name_nested(tmp_path, 2000, "small.py"))
    large = elapsed(_same_name_nested(tmp_path, 4000, "large.py"))
    # 입력 2배에 시간 2배 근처여야 한다 (2차면 4배). 환경 변동 고려해 3배 상한.
    assert large < max(small * 3, 0.05), (small, large)


def test_same_name_nesting_returns_outermost_span(tmp_path: Path) -> None:
    p = _same_name_nested(tmp_path, 3, "nested.py")
    blocks = extract_anchor_blocks(p)
    # 바깥 블록이 최종값 — 안쪽 마커들을 본문에 품는다
    assert "x = 1" in blocks["A"]
    assert blocks["A"].count("ANCHOR: A_START") == 2


def test_line_ranges_same_name_nesting_matches_blocks(tmp_path: Path) -> None:
    """같은 이름이 겹쳐 열릴 때 두 파서가 같은 구간을 고른다."""
    text = (
        "# === ANCHOR: A_START ===\n"
        "outer_head = 1\n"
        "# === ANCHOR: A_START ===\n"
        "inner = 2\n"
        "# === ANCHOR: A_END ===\n"
        "outer_tail = 3\n"
        "# === ANCHOR: A_END ===\n"
    )
    p = tmp_path / "dup.py"
    p.write_text(text, encoding="utf-8")

    start_line, end_line = extract_anchor_line_ranges(p)["A"]
    assert (start_line, end_line) == (1, 7)  # 바깥 구간
    assert dict(iter_anchor_blocks(p))["A"] == extract_anchor_blocks(p)["A"]
