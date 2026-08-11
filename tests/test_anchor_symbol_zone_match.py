# === ANCHOR: TEST_ANCHOR_SYMBOL_ZONE_MATCH_START ===
"""교차하지 않는 단독 오배치 앵커를 잡는다 (issue #11).

교차 검출은 앵커가 **둘 이상 엇갈릴 때만** 잡는다. 앵커 하나가 혼자 잘못
놓이면 짝도 맞고 교차도 없어 검증을 통과한다. 그런데 그 앵커가 보호하는 건
함수 본문이 아니라 시그니처 한 조각이다 — AI 에게 "이 앵커 안에서만 고쳐라"
라고 하면 본문은 보호 밖이다.

원인은 #7 에서 고친 생성기 결함(여러 줄 시그니처의 닫는 괄호를 본문 끝으로
오인)이다. 원인은 제거됐지만 이미 놓인 마커는 그대로 남는다.

오탐 경계가 이 검사의 핵심이다. **덜 덮는 것만** 문제다 — 앵커가 심볼보다
넓은 건(이웃 헬퍼·모듈 상수를 한 구역으로 묶은 경우) 사람의 의도이고
보호가 더 넓어질 뿐이다. 그것까지 보고하면 정작 위험한 "부족"이 묻힌다.
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchors,
    find_crossing_anchors,
    find_misplaced_anchors,
    repair_crossing_anchors,
)


def _write(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    return p


def test_end_marker_inside_multiline_signature_is_reported(tmp_path: Path) -> None:
    """issue #11 의 실제 사례 — END 가 인자 목록 한가운데 있다."""
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(\n"
        "    first: int,\n"
        "    second: int,\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n"
        ") -> int:\n"
        "    total = first + second\n"
        "    return total\n",
    )

    # 짝도 맞고 교차도 없다 — 기존 검사로는 통과한다.
    assert find_crossing_anchors(path.read_text(encoding="utf-8")) == []

    problems = find_misplaced_anchors(path)
    assert len(problems) == 1
    assert "SAMPLE_HANDLE" in problems[0]
    assert "다 덮지 못합니다" in problems[0]


def test_anchor_covering_whole_symbol_is_not_reported(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(\n"
        "    first: int,\n"
        "    second: int,\n"
        ") -> int:\n"
        "    return first + second\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n",
    )

    assert find_misplaced_anchors(path) == []


def test_anchor_wider_than_symbol_is_not_reported(tmp_path: Path) -> None:
    """이웃 헬퍼·상수까지 한 구역으로 묶은 건 결함이 아니라 의도다.

    이걸 보고하면 이 리포만 해도 경고가 16건으로 부풀고 그중 12건이
    정당한 묶음이었다 — 위험한 4건이 그 안에 묻힌다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "LIMIT = 10\n"
        "\n"
        "\n"
        "def _helper(value: int) -> int:\n"
        "    return value * 2\n"
        "\n"
        "\n"
        "def handle(value: int) -> int:\n"
        "    return _helper(value) + LIMIT\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n",
    )

    assert find_misplaced_anchors(path) == []


def test_hand_placed_anchor_without_matching_symbol_is_skipped(tmp_path: Path) -> None:
    """대응 심볼이 없는 앵커는 비교 대상이 아니다.

    사람이 직접 건 구역이나 심볼명이 바뀐 뒤 남은 앵커가 여기 해당한다.
    이름이 생성 규칙과 정확히 일치할 때만 비교한다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_IMPORTS_START ===\n"
        "import os\n"
        "# === ANCHOR: SAMPLE_IMPORTS_END ===\n"
        "\n"
        "\n"
        "# === ANCHOR: SAMPLE_OLD_NAME_START ===\n"
        "def handle(value: int) -> int:\n"
        "    return value\n"
        "# === ANCHOR: SAMPLE_OLD_NAME_END ===\n",
    )

    assert find_misplaced_anchors(path) == []


def test_duplicate_symbol_names_match_any_candidate(tmp_path: Path) -> None:
    """다른 클래스의 동명 메서드는 같은 앵커 이름으로 수렴한다.

    어느 쪽을 가리키는지 가릴 수 없으므로, 하나라도 덮으면 제자리로 본다.
    여기서 오배치로 단정하면 정상 파일을 깨뜨린다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "class First:\n"
        "    # === ANCHOR: SAMPLE_RUN_START ===\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "    # === ANCHOR: SAMPLE_RUN_END ===\n"
        "\n"
        "\n"
        "class Second:\n"
        "    def run(self) -> int:\n"
        "        return 2\n",
    )

    assert find_misplaced_anchors(path) == []


def test_typescript_end_before_return_is_reported(tmp_path: Path) -> None:
    """실제로 이 리포의 tree.ts 가 이 모양이었다 — 반환문이 보호 밖이다."""
    path = _write(
        tmp_path,
        "tree.ts",
        "// === ANCHOR: TREE_FLATTEN_START ===\n"
        "export function flatten(root: Node): Item[] {\n"
        "  const result: Item[] = [];\n"
        "  visit(root, 0);\n"
        "// === ANCHOR: TREE_FLATTEN_END ===\n"
        "  return result;\n"
        "}\n",
    )

    problems = find_misplaced_anchors(path)
    assert len(problems) == 1
    assert "TREE_FLATTEN" in problems[0]


def test_repair_fixes_misplacement_without_any_crossing(tmp_path: Path) -> None:
    """교차가 없어도 고쳐야 한다 — #11 이 요구한 대상 확대."""
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(\n"
        "    first: int,\n"
        "    second: int,\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n"
        ") -> int:\n"
        "    total = first + second\n"
        "    return total\n",
    )
    assert find_crossing_anchors(path.read_text(encoding="utf-8")) == []
    before = set(extract_anchors(path))

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "repaired"
    assert find_misplaced_anchors(path) == []
    # 이름은 그대로여야 한다. intent 가 이름을 키로 붙어 있다.
    assert set(extract_anchors(path)) == before
    # 코드는 한 줄도 잃지 않는다.
    body = path.read_text(encoding="utf-8")
    assert "total = first + second" in body
    assert "return total" in body


def test_repair_does_not_move_a_disjoint_hand_placed_anchor(tmp_path: Path) -> None:
    """보고 기준과 이동 기준은 달라야 한다.

    이름이 생성 규칙과 우연히 같으면서 사람이 전혀 다른 곳에 일부러 건
    앵커가 있다. "심볼을 다 덮지 못한다" 로 옮길 대상을 정하면 이런 앵커가
    끌려가고, 사용자가 지정한 보호 구역이 조용히 사라진다.

    옮기는 건 심볼과 **겹칠** 때만이다 — 겹침은 그 심볼을 감싸려다 경계를
    잘못 잡았다는 뜻이고, 그게 #7 생성기 결함이 남긴 모양이다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        # SAMPLE_HELPER 는 이름이 생성 규칙과 같지만 손으로 상수에 걸어뒀다.
        "# === ANCHOR: SAMPLE_HELPER_START ===\n"
        "SENTINEL = 1\n"
        "# === ANCHOR: SAMPLE_HELPER_END ===\n"
        "\n"
        "\n"
        "def helper() -> int:\n"
        "    return 2\n",
    )
    original = path.read_text(encoding="utf-8")

    # 보고는 된다 — 이름이 가리키는 심볼을 덮고 있지 않으니 알려줄 값어치가 있다.
    assert len(find_misplaced_anchors(path)) == 1

    # 그러나 옮기지는 않는다.
    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)
    assert outcome["status"] == "unchanged"
    assert path.read_text(encoding="utf-8") == original


def test_repair_is_not_abandoned_because_of_an_unfixable_report(tmp_path: Path) -> None:
    """고칠 수 없는 보고 1건 때문에 고칠 수 있는 파일을 포기하면 안 된다.

    재생성 후에도 손수 앵커는 계속 보고된다. 그걸 "아직 오배치가 남았다" 로
    읽고 건너뛰면 같은 파일의 진짜 결함이 영영 안 고쳐진다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HELPER_START ===\n"
        "SENTINEL = 1\n"
        "# === ANCHOR: SAMPLE_HELPER_END ===\n"
        "\n"
        "\n"
        "def helper() -> int:\n"
        "    return 2\n"
        "\n"
        "\n"
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(\n"
        "    value: int,\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n"
        ") -> int:\n"
        "    return value\n",
    )

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "repaired"
    remaining = find_misplaced_anchors(path)
    # 진짜 결함은 사라지고, 손수 앵커 보고만 남는다.
    assert len(remaining) == 1
    assert "SAMPLE_HELPER" in remaining[0]
    assert "SENTINEL = 1" in path.read_text(encoding="utf-8")


def test_repair_leaves_clean_file_untouched(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(value: int) -> int:\n"
        "    return value\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n",
    )
    original = path.read_text(encoding="utf-8")

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "unchanged"
    assert path.read_text(encoding="utf-8") == original


# === ANCHOR: TEST_ANCHOR_SYMBOL_ZONE_MATCH_END ===
