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
    extract_anchor_blocks,
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


def test_second_occurrence_of_a_duplicate_name_is_checked(tmp_path: Path) -> None:
    """같은 이름이 두 번 열리면 두 번째가 검사에서 빠지던 결함.

    extract_anchor_line_ranges 는 두 번째 등장을 NAME_2 로 이름 붙이는데,
    심볼 쪽은 둘 다 NAME 으로만 색인된다. 그대로 찾으면 아무 심볼과도 안
    맞아 조용히 건너뛰어졌다 — 잘린 두 번째 앵커가 영영 안 잡힌다.
    """
    path = _write(
        tmp_path,
        "dup.py",
        "class First:\n"
        "    # === ANCHOR: DUP_RUN_START ===\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "    # === ANCHOR: DUP_RUN_END ===\n"
        "\n"
        "\n"
        "class Second:\n"
        "    # === ANCHOR: DUP_RUN_START ===\n"
        "    def run(self) -> int:\n"
        "        value = 2\n"
        "    # === ANCHOR: DUP_RUN_END ===\n"  # 잘렸다 — return 이 보호 밖
        "        return value\n",
    )

    problems = find_misplaced_anchors(path)
    assert len(problems) == 1
    assert "DUP_RUN_2" in problems[0]
    # 대표 심볼은 겹치는 쪽이어야 한다. 첫 번째를 쓰면 엉뚱한 줄을 가리키고
    # 겹침 판정(옮길지 말지)까지 틀린다.
    assert "10~13번째 줄" in problems[0]

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)
    assert outcome["status"] == "repaired"
    assert find_misplaced_anchors(path) == []
    body = path.read_text(encoding="utf-8")
    assert "return 1" in body
    assert "return value" in body


def test_repair_skips_when_a_sibling_occurrence_would_shrink(tmp_path: Path) -> None:
    """같은 이름의 정상인 등장이 줄어들 위험이 있으면 통째로 건너뛴다.

    마커를 걷어내는 건 이름 단위다. 두 번째 등장을 고치려고 걷어내면 정상인
    첫 번째까지 함께 지워졌다가 심볼 크기로 다시 놓인다 — 사람이 이웃 상수까지
    넓게 걸어둔 구역이 조용히 줄어든다.

    면제를 마커 이름 단위로 주면 drift 가드가 이걸 못 잡는다. 지목된 **그
    등장**에만 면제를 줘야 한다.
    """
    path = _write(
        tmp_path,
        "dup.py",
        # 첫 번째는 사람이 상수까지 넓게 걸어둔 정상 구역.
        "# === ANCHOR: DUP_RUN_START ===\n"
        "LIMIT = 5\n"
        "\n"
        "\n"
        "def run() -> int:\n"
        "    return LIMIT\n"
        "# === ANCHOR: DUP_RUN_END ===\n"
        "\n"
        "\n"
        "class Second:\n"
        "    # === ANCHOR: DUP_RUN_START ===\n"
        "    def run(self) -> int:\n"
        "        value = 2\n"
        "    # === ANCHOR: DUP_RUN_END ===\n"  # 잘렸다
        "        return value\n",
    )
    original = path.read_text(encoding="utf-8")

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "skipped"
    assert path.read_text(encoding="utf-8") == original
    # 넓게 걸어둔 보호 구역은 그대로다.
    assert "LIMIT = 5" in extract_anchor_blocks(path)["DUP_RUN"]


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


def test_decorator_is_part_of_the_symbol(tmp_path: Path) -> None:
    """데코레이터를 심볼에서 빼면 마커가 @route 와 def 사이에 박힌다.

    그 앵커만 보고 고치는 AI 는 이 함수가 라우트인 줄도 모른다. 더 나쁜 건
    repair 가 사람이 데코레이터 위에 걸어둔 START 를 그 아래로 끌어내리면서
    "고쳤다" 고 보고하는 경로다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "@route\n"
        "def handle() -> int:\n"
        "    return 1\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n",
    )

    # 데코레이터까지 덮고 있으니 정상이다.
    assert find_misplaced_anchors(path) == []

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)
    assert outcome["status"] == "unchanged"
    assert "@route" in extract_anchor_blocks(path)["SAMPLE_HANDLE"]


def test_decorator_left_outside_is_reported(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "sample.py",
        "@route\n"
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle() -> int:\n"
        "    return 1\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n",
    )

    problems = find_misplaced_anchors(path)
    assert len(problems) == 1
    assert "SAMPLE_HANDLE" in problems[0]

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)
    assert outcome["status"] == "repaired"
    assert "@route" in extract_anchor_blocks(path)["SAMPLE_HANDLE"]


def test_repair_does_not_create_new_anchors(tmp_path: Path) -> None:
    """repair 는 옮기기만 한다 — 보호 계약을 넓히지 않는다.

    걷어낸 건 대상 마커뿐이지만 생성기는 파일 전체를 훑는다. 그대로 두면
    앵커가 없던 함수·클래스에도 새로 붙는다. 이 리포를 한 번 돌렸을 때
    20개 파일에 139개가 붙었다 — "마커를 옮긴다" 고 한 명령의 결과로는
    설명되지 않는 변경이다.
    """
    path = _write(
        tmp_path,
        "sample.py",
        "# === ANCHOR: SAMPLE_HANDLE_START ===\n"
        "def handle(\n"
        "    value: int,\n"
        "# === ANCHOR: SAMPLE_HANDLE_END ===\n"
        ") -> int:\n"
        "    return value\n"
        "\n"
        "\n"
        "def untouched() -> int:\n"  # 앵커 없음 — 그대로여야 한다
        "    return 0\n",
    )
    before = set(extract_anchors(path))

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "repaired"
    assert set(extract_anchors(path)) == before
    assert "SAMPLE_UNTOUCHED" not in path.read_text(encoding="utf-8")


def test_repair_skips_when_an_occurrence_would_disappear(tmp_path: Path) -> None:
    """이름 집합만 보면 등장 횟수가 줄어드는 걸 놓친다.

    같은 이름이 한 심볼에 두 번 걸려 있으면 걷어내기는 둘 다 지우는데 생성기는
    한 쌍만 다시 놓는다. 이름은 살아 있으니 소실 검사를 통과하고, 두 등장 모두
    오배치로 지목돼 drift 면제까지 받아 NAME_2 가 말없이 사라진다.
    """
    path = _write(
        tmp_path,
        "dup.py",
        "def run(\n"
        "# === ANCHOR: DUP_RUN_START ===\n"
        "    a: int,\n"
        "# === ANCHOR: DUP_RUN_END ===\n"
        "# === ANCHOR: DUP_RUN_START ===\n"
        "    b: int,\n"
        "# === ANCHOR: DUP_RUN_END ===\n"
        ") -> int:\n"
        "    return a + b\n",
    )
    original = path.read_text(encoding="utf-8")

    outcome = repair_crossing_anchors(tmp_path, path, dry_run=False)

    assert outcome["status"] == "skipped"
    assert "DUP_RUN_2" in outcome["lost_names"]
    assert path.read_text(encoding="utf-8") == original


def test_pathological_js_nesting_is_bounded_and_reported(tmp_path: Path) -> None:
    """JS 블록 탐지는 중첩에 초선형이다 — 상한을 두되 조용히 넘기지 않는다.

    실측: 중첩 50/100/200/400개가 0.018/0.13/0.98/7.9초. 생성기(`--auto`)는
    원래 이 비용을 치렀지만 배치 검사가 읽기 전용인 `--validate` 까지 그
    비용을 끌고 들어왔다 — 파일 하나로 검사 전체를 멈춰 세울 수 있다.
    """
    depth = 400
    body = "".join(f"{'  ' * i}function f{i}() {{\n" for i in range(depth))
    body += "".join(f"{'  ' * (depth - 1 - i)}}}\n" for i in range(depth))
    path = _write(tmp_path, "deep.ts", body)

    problems = find_misplaced_anchors(path)

    assert len(problems) == 1
    assert "건너뜁니다" in problems[0]
    # 건너뛴 파일은 고치려 들지도 않는다.
    assert repair_crossing_anchors(tmp_path, path, dry_run=True)["status"] == "unchanged"


def test_regex_literal_braces_do_not_end_the_block(tmp_path: Path) -> None:
    """정규식 안의 중괄호를 코드로 세면 함수가 일찍 끝난 것으로 잡힌다.

    이 리포의 customStyles.ts 가 그랬다. `s.replace(/\\}$/, ...)` 의 `}` 때문에
    블록 깊이가 0으로 떨어져 END 가 `return s;` 앞에 놓였고, 검사조차 그걸
    정상으로 봤다 — 결함을 못 보는 검사는 없는 것보다 나쁘다.
    """
    path = _write(
        tmp_path,
        "styles.ts",
        "// === ANCHOR: STYLES_BUILD_START ===\n"
        "export function build(t: string): string {\n"
        "  let s = t;\n"
        "  if (t) {\n"
        "    s = s.replace(/\\}$/, ';}');\n"
        "  }\n"
        "// === ANCHOR: STYLES_BUILD_END ===\n"
        "  return s;\n"
        "}\n",
    )

    problems = find_misplaced_anchors(path)
    assert len(problems) == 1
    assert "STYLES_BUILD" in problems[0]

    assert repair_crossing_anchors(tmp_path, path, dry_run=False)["status"] == "repaired"
    assert "return s;" in extract_anchor_blocks(path)["STYLES_BUILD"]


def test_division_is_not_mistaken_for_a_regex(tmp_path: Path) -> None:
    """반대 방향 오판도 막아야 한다 — 나눗셈을 정규식으로 읽으면 깊이가 샌다."""
    path = _write(
        tmp_path,
        "math.ts",
        "// === ANCHOR: MATH_RATIO_START ===\n"
        "export function ratio(a: number, b: number): number {\n"
        "  const half = (a + 1) / 2 / b;\n"
        "  return half;\n"
        "}\n"
        "// === ANCHOR: MATH_RATIO_END ===\n",
    )

    assert find_misplaced_anchors(path) == []


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
