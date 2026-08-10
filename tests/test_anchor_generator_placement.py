# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_START ===
"""`vib anchor --auto` 가 교차 앵커를 만들면 안 된다 (issue #7).

교차는 한쪽 블록이 다른 앵커의 여는 마커만 품는 상태다. 그 블록을 고치면
상대 경계가 깨지는데 짝은 맞아 validate 를 통과한다. 이 리포에만 39건이
있었고 전부 생성기가 스스로 만든 것이었다 — 결함 3종:

1. 여러 줄 시그니처의 닫는 괄호가 def 와 같은 열이라 그 앞줄을 본문 끝으로 오인
2. 중첩 심볼을 하나씩 끼워넣어 바깥 END 위치가 밀림 (JS 쪽은 이미 고쳐져 있었다)
3. 같은 위치에서 START/END 삽입 순서가 뒤집혀 한 줄짜리 메서드가 연달아 있을 때 엇갈림
"""

from __future__ import annotations

from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchors,
    find_crossing_anchors,
    insert_js_symbol_anchors,
    insert_module_anchors,
    insert_python_symbol_anchors,
    repair_crossing_anchors,
)


def _py(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    insert_python_symbol_anchors(p)
    return p


# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_TESTNOCROSSINGGENERATED_START ===
class TestNoCrossingGenerated:
    def test_multiline_signature(self, tmp_path: Path) -> None:
        """닫는 괄호가 def 와 같은 열이라 본문 끝으로 오인됐다."""
        p = _py(
            tmp_path,
            "wide.py",
            "def wide(\n    a: int,\n    b: int = 1,\n) -> int:\n    return a + b\n",
        )
        text = p.read_text(encoding="utf-8")
        assert find_crossing_anchors(text) == []
        # END 는 본문 뒤에 와야 한다 — 시그니처 한가운데가 아니라
        lines = text.splitlines()
        end_at = next(i for i, x in enumerate(lines) if "WIDE_WIDE_END" in x)
        body_at = next(i for i, x in enumerate(lines) if "return a + b" in x)
        assert end_at > body_at

    def test_nested_symbols(self, tmp_path: Path) -> None:
        """안쪽 마커 삽입이 바깥 END 위치를 밀었다."""
        p = _py(
            tmp_path,
            "nested.py",
            "class Outer:\n    def inner(self) -> None:\n        pass\n",
        )
        assert find_crossing_anchors(p.read_text(encoding="utf-8")) == []

    def test_consecutive_one_line_methods(self, tmp_path: Path) -> None:
        """같은 위치에서 앞 블록 END 가 다음 블록 START 보다 뒤에 놓였다."""
        p = _py(
            tmp_path,
            "proto.py",
            "class C(Protocol):\n"
            "    async def __aenter__(self) -> object: ...\n"
            "    async def __aexit__(self, exc: object) -> bool: ...\n",
        )
        assert find_crossing_anchors(p.read_text(encoding="utf-8")) == []

    def test_deeply_nested_and_decorated(self, tmp_path: Path) -> None:
        p = _py(
            tmp_path,
            "deep.py",
            "class A:\n"
            "    @property\n"
            "    def value(self) -> int:\n"
            "        def helper(\n"
            "            x: int,\n"
            "        ) -> int:\n"
            "            return x\n"
            "        return helper(1)\n",
        )
        text = p.read_text(encoding="utf-8")
        assert find_crossing_anchors(text) == []
        names = set(extract_anchors(p))
        assert {"DEEP_A", "DEEP_VALUE", "DEEP_HELPER"} <= names

    def test_syntax_error_falls_back_without_crashing(self, tmp_path: Path) -> None:
        # AST 를 못 쓰면 기존 들여쓰기 스캔으로 떨어진다 — 죽지만 않으면 된다.
        p = tmp_path / "broken.py"
        p.write_text("def f(:\n    pass\n", encoding="utf-8")
        _ = insert_python_symbol_anchors(p)


# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_TESTNOCROSSINGGENERATED_END ===


# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_TESTREPAIR_START ===
class TestRepair:
    """마커 위치를 옮기는 것은 코드 변경이라 안전장치가 있어야 한다."""

    def _crossing_file(self, tmp_path: Path) -> Path:
        marker = "=" * 3
        p = tmp_path / "mod.py"
        p.write_text(
            f"# {marker} ANCHOR: MOD_START {marker}\n"
            f"# {marker} ANCHOR: MOD_OUTER_START {marker}\n"
            "class Outer:\n"
            f"    # {marker} ANCHOR: MOD_INNER_START {marker}\n"
            f"# {marker} ANCHOR: MOD_OUTER_END {marker}\n"
            "    def inner(self) -> None:\n"
            "        pass\n"
            f"    # {marker} ANCHOR: MOD_INNER_END {marker}\n"
            f"# {marker} ANCHOR: MOD_END {marker}\n",
            encoding="utf-8",
        )
        return p

    def test_repair_removes_crossing(self, tmp_path: Path) -> None:
        p = self._crossing_file(tmp_path)
        assert find_crossing_anchors(p.read_text(encoding="utf-8"))
        result = repair_crossing_anchors(tmp_path, p)
        assert result["status"] == "repaired"
        assert find_crossing_anchors(p.read_text(encoding="utf-8")) == []

    def test_dry_run_changes_nothing(self, tmp_path: Path) -> None:
        p = self._crossing_file(tmp_path)
        before = p.read_text(encoding="utf-8")
        result = repair_crossing_anchors(tmp_path, p, dry_run=True)
        assert result["status"] == "repaired"
        assert p.read_text(encoding="utf-8") == before

    def test_skips_when_a_name_would_be_lost(self, tmp_path: Path) -> None:
        """사람이 붙인 이름이나 심볼명이 바뀐 뒤 남은 앵커는 재생성으로 못 되살린다.

        그걸 잃으면 intent 와 보호 구역이 함께 날아간다 — 건너뛰고 알린다.
        """
        marker = "=" * 3
        p = tmp_path / "custom.py"
        p.write_text(
            f"# {marker} ANCHOR: CUSTOM_START {marker}\n"
            f"# {marker} ANCHOR: CUSTOM_OUTER_START {marker}\n"
            "class Outer:\n"
            f"    # {marker} ANCHOR: HANDWRITTEN_ZONE_START {marker}\n"
            f"# {marker} ANCHOR: CUSTOM_OUTER_END {marker}\n"
            "    def inner(self) -> None:\n"
            "        pass\n"
            f"    # {marker} ANCHOR: HANDWRITTEN_ZONE_END {marker}\n"
            f"# {marker} ANCHOR: CUSTOM_END {marker}\n",
            encoding="utf-8",
        )
        before = p.read_text(encoding="utf-8")
        result = repair_crossing_anchors(tmp_path, p)
        assert result["status"] == "skipped"
        assert "HANDWRITTEN_ZONE" in result["lost_names"]
        assert p.read_text(encoding="utf-8") == before

    def test_skips_when_an_unrelated_zone_would_move(self, tmp_path: Path) -> None:
        """이름이 남았다고 같은 구역인 건 아니다.

        사람이 붙인 앵커의 이름이 우연히 생성 규칙과 같으면, 이름은 살아남으면서
        보호 구역만 조용히 다른 코드로 옮겨간다.
        """
        marker = "=" * 3
        p = tmp_path / "drift.py"
        # DRIFT_HELPER 는 이름이 생성 규칙과 같지만 손으로 다른 구역에 걸어뒀다.
        p.write_text(
            f"# {marker} ANCHOR: DRIFT_START {marker}\n"
            f"# {marker} ANCHOR: DRIFT_HELPER_START {marker}\n"
            "SENTINEL = 1\n"
            f"# {marker} ANCHOR: DRIFT_HELPER_END {marker}\n"
            f"# {marker} ANCHOR: DRIFT_OUTER_START {marker}\n"
            "class Outer:\n"
            f"    # {marker} ANCHOR: DRIFT_INNER_START {marker}\n"
            f"# {marker} ANCHOR: DRIFT_OUTER_END {marker}\n"
            "    def inner(self) -> None:\n"
            "        pass\n"
            f"    # {marker} ANCHOR: DRIFT_INNER_END {marker}\n"
            "def helper() -> int:\n"
            "    return 2\n"
            f"# {marker} ANCHOR: DRIFT_END {marker}\n",
            encoding="utf-8",
        )
        before = p.read_text(encoding="utf-8")
        result = repair_crossing_anchors(tmp_path, p)
        assert result["status"] == "skipped"
        assert "DRIFT_HELPER" in result["reason"]
        assert p.read_text(encoding="utf-8") == before

    def test_write_is_atomic(self, tmp_path: Path) -> None:
        """마커만 옮기려다 소스를 잃으면 안 된다 — write_text 는 먼저 비운다."""
        from vibelign.core import atomic_write as atomic_write_mod

        p = self._crossing_file(tmp_path)
        before = p.read_text(encoding="utf-8")
        calls: list[str] = []
        real_replace = atomic_write_mod.os.replace

        def track(src: object, dst: object) -> None:
            calls.append(Path(str(dst)).name)
            real_replace(src, dst)  # type: ignore[arg-type]

        import pytest as _pytest

        with _pytest.MonkeyPatch.context() as mp:
            mp.setattr(atomic_write_mod.os, "replace", track)
            result = repair_crossing_anchors(tmp_path, p)

        assert result["status"] == "repaired"
        assert calls == ["mod.py"]  # 원자적 교체를 거쳤다
        assert p.read_text(encoding="utf-8") != before

    def test_untouched_when_no_crossing(self, tmp_path: Path) -> None:
        p = tmp_path / "clean.py"
        p.write_text("def f() -> int:\n    return 1\n", encoding="utf-8")
        insert_module_anchors(p)
        insert_python_symbol_anchors(p)
        before = p.read_text(encoding="utf-8")
        result = repair_crossing_anchors(tmp_path, p)
        assert result["status"] == "unchanged"
        assert p.read_text(encoding="utf-8") == before

    def test_js_files_are_handled(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.ts"
        p.write_text(
            "export function outer(): void {\n  const x = 1;\n}\n", encoding="utf-8"
        )
        insert_module_anchors(p)
        insert_js_symbol_anchors(p)
        assert find_crossing_anchors(p.read_text(encoding="utf-8")) == []


# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_TESTREPAIR_END ===
# === ANCHOR: TEST_ANCHOR_GENERATOR_PLACEMENT_END ===
