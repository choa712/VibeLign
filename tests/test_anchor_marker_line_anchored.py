# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_START ===
"""마커는 '줄 전체가 마커인 주석'일 때만 앵커 경계다 (issue #4).

패턴이 줄 단위로 고정되지 않으면 소스 텍스트 안에 우연히(또는 고의로) 들어간
마커 모양 문자열이 진짜 경계로 인식돼, 블록이 의도보다 짧게 잘리고 바깥
구간이 보호 없이 남는다. validate 는 START/END 쌍이 맞는 것으로 보여 조용하다.
"""

from __future__ import annotations

import re
from pathlib import Path

from vibelign.core.anchor_tools import (
    extract_anchor_blocks,
    extract_anchor_spans,
    extract_anchors,
)
from vibelign.core.structure_policy import ANCHOR_MARKER_PATTERN

MARKER = "=" * 3 + " ANCHOR: {name} " + "=" * 3


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_TESTINLINEMARKERISNOTABOUNDARY_START ===
class TestInlineMarkerIsNotABoundary:
    """줄 안쪽에 박힌 마커는 경계가 아니다."""

    def test_marker_inside_string_literal_does_not_close_block(
        self, tmp_path: Path
    ) -> None:
        # 문자열 리터럴 안의 END 가 앵커를 그 자리에서 닫으면
        # 그 아래 protected_value 가 보호 구역 밖으로 밀려난다.
        src = "\n".join(
            [
                f"# {MARKER.format(name='A_START')}",
                f'msg = "보호구역 종료: {MARKER.format(name="A_END")}"',
                "protected_value = 42",
                f"# {MARKER.format(name='A_END')}",
                "",
            ]
        )
        p = _write(tmp_path, "mod.py", src)

        blocks = extract_anchor_blocks(p)
        assert "protected_value = 42" in blocks["A"]

    def test_marker_after_code_on_same_line_is_ignored(self, tmp_path: Path) -> None:
        src = "\n".join(
            [
                f"// {MARKER.format(name='B_START')}",
                f'const s = "x";  // {MARKER.format(name="B_END")}',
                "const keep = 1;",
                f"// {MARKER.format(name='B_END')}",
                "",
            ]
        )
        p = _write(tmp_path, "mod.ts", src)

        blocks = extract_anchor_blocks(p)
        assert "const keep = 1;" in blocks["B"]

    def test_trailing_content_after_marker_is_ignored(self, tmp_path: Path) -> None:
        # 마커 뒤에 다른 내용이 붙으면 마커가 아니다.
        src = "\n".join(
            [
                f"# {MARKER.format(name='C_START')} 이건 설명입니다",
                "x = 1",
                f"# {MARKER.format(name='C_END')}",
                "",
            ]
        )
        p = _write(tmp_path, "mod.py", src)

        # START 가 인정되지 않으므로 짝 없는 END 만 남아 span 이 생기지 않는다.
        assert extract_anchor_spans(p) == []

    def test_span_line_numbers_unchanged_by_indent(self, tmp_path: Path) -> None:
        # 패턴이 줄 시작으로 이동해도 줄 번호 계산이 흔들리면 안 된다.
        src = "\n".join(
            [
                "def f():",
                f"    # {MARKER.format(name='D_START')}",
                "    return 1",
                f"    # {MARKER.format(name='D_END')}",
                "",
            ]
        )
        p = _write(tmp_path, "mod.py", src)

        spans = extract_anchor_spans(p)
        assert [(s["name"], s["start"], s["end"]) for s in spans] == [("D", 2, 4)]


# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_TESTINLINEMARKERISNOTABOUNDARY_END ===


# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_TESTGENUINEMARKERSSTILLPARSE_START ===
class TestGenuineMarkersStillParse:
    """생성기가 실제로 뱉는 4가지 형태는 전부 그대로 인정돼야 한다."""

    def test_all_generated_shapes(self, tmp_path: Path) -> None:
        src = "\n".join(
            [
                f"# {MARKER.format(name='PY_START')}",
                f"    # {MARKER.format(name='PY_INNER_START')}",
                "    pass",
                f"    # {MARKER.format(name='PY_INNER_END')}",
                f"# {MARKER.format(name='PY_END')}",
                "",
            ]
        )
        p = _write(tmp_path, "a.py", src)
        assert extract_anchors(p) == ["PY", "PY_INNER"]

        src_ts = "\n".join(
            [
                f"// {MARKER.format(name='TS_START')}",
                f"  // {MARKER.format(name='TS_INNER_START')}",
                "  const x = 1;",
                f"  // {MARKER.format(name='TS_INNER_END')}",
                f"// {MARKER.format(name='TS_END')}",
                "",
            ]
        )
        q = _write(tmp_path, "a.ts", src_ts)
        assert extract_anchors(q) == ["TS", "TS_INNER"]

    def test_crlf_line_endings(self, tmp_path: Path) -> None:
        # Windows 체크아웃에서 CRLF 로 저장된 파일도 인정돼야 한다.
        # (universal-newline 변환을 우회해 raw CRLF 를 쓴다)
        p = tmp_path / "crlf.py"
        body = (
            f"# {MARKER.format(name='CR_START')}\r\n"
            "x = 1\r\n"
            f"# {MARKER.format(name='CR_END')}\r\n"
        )
        p.write_bytes(body.encode("utf-8"))
        assert extract_anchors(p) == ["CR"]

    def test_pattern_matches_raw_marker_line_directly(self) -> None:
        rx = re.compile(ANCHOR_MARKER_PATTERN)
        assert rx.search(f"# {MARKER.format(name='X_START')}")
        assert rx.search(f"\t// {MARKER.format(name='X_END')}")
        assert not rx.search(f'v = "// {MARKER.format(name="X_END")}"')


# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_TESTGENUINEMARKERSSTILLPARSE_END ===
# === ANCHOR: TEST_ANCHOR_MARKER_LINE_ANCHORED_END ===
