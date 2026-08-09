# === ANCHOR: TEST_ANCHOR_PARSER_SINGLE_SOURCE_START ===
"""앵커를 읽는 규칙은 한 곳에서만 나와야 한다.

이 리포에는 "앵커가 있는가 / 어디까지가 앵커인가" 를 각자 판정하는 코드가
9곳 있었다 — 정본 정규식 2, 부분 문자열 3, 느슨한 정규식 3, 그리고 파괴적인
strip_anchors 1. 그래서 같은 파일이 어느 경로로 보느냐에 따라 보호됨/안 됨이
갈렸고, `vib scan --auto` 는 정상 코드를 지웠다.

새 모듈이 자기 정규식을 하나 더 만들면 그 균열이 되살아난다. 소스에서 막는다.
검사는 AST 로 한다 — 텍스트 매칭은 이 파일의 설명문과 다른 모듈의 독스트링을
오탐해서, 오탐을 피하려다 규칙 자체가 헐거워진다.
"""

from __future__ import annotations

import ast
from pathlib import Path

from vibelign.core.structure_policy import ANCHOR_MARKER_PATTERN

# 정본 패턴을 소유·구현하는 모듈. 여기서만 ANCHOR 정규식을 정의한다.
_ALLOWED = {
    Path("vibelign/core/structure_policy.py"),  # 패턴 정의
    Path("vibelign/core/anchor_tools.py"),  # 정본 파서 + 훼손 마커 검출
    Path("vibelign/core/fast_tools.py"),  # rg 가속 경로 (같은 패턴 재사용)
}

_RE_FUNCS = {"compile", "search", "match", "findall", "finditer", "sub", "fullmatch"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _python_sources() -> list[Path]:
    root = _repo_root()
    return sorted(
        p.relative_to(root)
        for p in (root / "vibelign").rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _string_args(node: ast.Call) -> list[str]:
    return [
        arg.value
        for arg in node.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]


def _is_re_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _RE_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "re"
    )


# === ANCHOR: TEST_ANCHOR_PARSER_SINGLE_SOURCE_TESTSINGLESOURCE_START ===
class TestSingleSource:
    def test_no_module_defines_its_own_anchor_regex(self) -> None:
        root = _repo_root()
        offenders: list[str] = []
        for rel in _python_sources():
            if rel in _ALLOWED:
                continue
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _is_re_call(node):
                    continue
                if any("ANCHOR" in value for value in _string_args(node)):
                    offenders.append(f"{rel}:{node.lineno}")
        assert offenders == [], (
            "앵커 정규식을 자체 정의한 모듈이 있습니다. "
            "structure_policy.has_anchor_markers 또는 anchor_tools 의 파서를 쓰세요: "
            + ", ".join(offenders)
        )

    def test_no_module_uses_substring_anchor_detection(self) -> None:
        """`"=== ANCHOR:" in text` 같은 판정을 막는다.

        문자열 리터럴에 마커 예시를 담은 파일이 "앵커 있음" 으로 잡혀
        영영 보호 대상에서 빠졌다 (실제로 테스트 파일 14개가 그랬다).
        """
        root = _repo_root()
        offenders: list[str] = []
        for rel in _python_sources():
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(
                    isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
                ):
                    continue
                left = node.left
                if (
                    isinstance(left, ast.Constant)
                    and isinstance(left.value, str)
                    and "ANCHOR:" in left.value
                ):
                    offenders.append(f"{rel}:{node.lineno}")
        assert offenders == [], (
            "부분 문자열로 앵커 유무를 판정하는 곳이 있습니다. "
            "문자열 리터럴 속 마커가 '앵커 있음' 으로 잡힙니다: " + ", ".join(offenders)
        )

    def test_canonical_pattern_is_line_anchored(self) -> None:
        # 줄 고정이 풀리면 소스 텍스트가 경계를 위조할 수 있다 (issue #4).
        assert ANCHOR_MARKER_PATTERN.startswith("^")
        assert ANCHOR_MARKER_PATTERN.endswith("$")

    def test_the_detector_actually_fires(self) -> None:
        """탐지기가 실제로 작동하는지 — 빈 결과가 '통과'로 위장하면 안 된다."""
        tree = ast.parse('import re\nP = re.compile(r"ANCHOR: (X)")\n')
        found = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _is_re_call(node)
            and any("ANCHOR" in value for value in _string_args(node))
        ]
        assert len(found) == 1

        tree2 = ast.parse('if "=== ANCHOR:" in text:\n    pass\n')
        hits = [
            node
            for node in ast.walk(tree2)
            if isinstance(node, ast.Compare)
            and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
            and "ANCHOR:" in node.left.value
        ]
        assert len(hits) == 1


# === ANCHOR: TEST_ANCHOR_PARSER_SINGLE_SOURCE_TESTSINGLESOURCE_END ===
# === ANCHOR: TEST_ANCHOR_PARSER_SINGLE_SOURCE_END ===
