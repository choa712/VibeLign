from pathlib import Path
from unittest.mock import MagicMock

from vibelign.core.anchor_tools import (
    extract_anchors,
    extract_anchor_blocks,
    extract_anchor_line_ranges,
    extract_anchor_spans,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestBug2PhantomSpans:
    def test_inline_mention_in_docstring_is_not_an_anchor(self, tmp_path: Path) -> None:
        text = '''"""
        Respect anchor boundaries (`ANCHOR: NAME_START` / `ANCHOR: NAME_END`)
        """

        # === ANCHOR: REAL_ONE_START ===
        x = 1
        # === ANCHOR: REAL_ONE_END ===
        '''
        p = _write(tmp_path, "mod.py", text)
        assert extract_anchors(p) == ["REAL_ONE"]
        spans = extract_anchor_spans(p)
        assert [s["name"] for s in spans] == ["REAL_ONE"]

    def test_inline_mention_in_line_comment_is_not_an_anchor(self, tmp_path: Path) -> None:
        text = (
            "# format: /abs/path/file.py:ANCHOR: FOO_START\n"
            "# === ANCHOR: REAL_TWO_START ===\n"
            "y = 2\n"
            "# === ANCHOR: REAL_TWO_END ===\n"
        )
        p = _write(tmp_path, "mod2.py", text)
        assert extract_anchors(p) == ["REAL_TWO"]
        spans = extract_anchor_spans(p)
        assert [s["name"] for s in spans] == ["REAL_TWO"]


class TestBug4DunderPreserved:
    def test_extract_anchors_preserves_dunder_suffix(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: CLI_BASE___INIT___START ===\n"
            "pass\n"
            "# === ANCHOR: CLI_BASE___INIT___END ===\n"
        )
        p = _write(tmp_path, "cli_base.py", text)
        assert extract_anchors(p) == ["CLI_BASE___INIT__"]

    def test_extract_anchor_blocks_preserves_dunder_suffix(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: __INIT___START ===\n"
            "pass\n"
            "# === ANCHOR: __INIT___END ===\n"
        )
        p = _write(tmp_path, "__init__.py", text)
        # extract_anchors 가 광고하는 이름으로 블록을 읽을 수 있어야 한다
        assert extract_anchors(p) == ["__INIT__"]
        assert set(extract_anchor_blocks(p)) == {"__INIT__"}
        assert set(extract_anchor_line_ranges(p)) == {"__INIT__"}

    def test_extract_anchor_spans_preserves_dunder_suffix(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: CLI_BASE___INIT___START ===\n"
            "pass\n"
            "# === ANCHOR: CLI_BASE___INIT___END ===\n"
        )
        p = _write(tmp_path, "cli_base.py", text)
        spans = extract_anchor_spans(p)
        assert len(spans) == 1
        assert spans[0]["name"] == "CLI_BASE___INIT__"
        assert spans[0]["start"] == 1
        assert spans[0]["end"] == 3


class TestBug3DanglingStartDropped:
    def test_unterminated_start_is_not_returned(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: GOOD_START ===\n"
            "ok = 1\n"
            "# === ANCHOR: GOOD_END ===\n"
            "\n"
            "# === ANCHOR: DANGLING_START ===\n"
            "oops = 2\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        names = [s["name"] for s in spans]
        assert names == ["GOOD"]
        assert all(s["end"] is not None for s in spans)


class TestBug1DuplicateNamesSuffixed:
    def test_duplicate_spans_get_numeric_suffix(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: DUP_START ===\n"
            "first = 1\n"
            "# === ANCHOR: DUP_END ===\n"
            "\n"
            "# === ANCHOR: DUP_START ===\n"
            "second = 2\n"
            "# === ANCHOR: DUP_END ===\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        names = [s["name"] for s in spans]
        assert names == ["DUP", "DUP_2"]
        assert spans[0]["start"] == 1 and spans[0]["end"] == 3
        assert spans[1]["start"] == 5 and spans[1]["end"] == 7


class TestBug5NestedAnchorBlocksDropped:
    """`vib anchor --auto`는 모듈 앵커 안에 심볼 앵커를 중첩 삽입한다.

    extract_anchor_blocks 가 단일 current_anchor 로 파싱하면 안쪽 START 가
    바깥 앵커를 덮어써 바깥 블록이 통째로 소실된다. 형제 함수
    extract_anchor_line_ranges 는 이름 매칭으로 이미 올바르게 처리한다.
    """

    NESTED = (
        "// === ANCHOR: OUTER_START ===\n"
        "const before = 1;\n"
        "// === ANCHOR: OUTER_INNER_START ===\n"
        "const inner = 2;\n"
        "// === ANCHOR: OUTER_INNER_END ===\n"
        "const after = 3;\n"
        "// === ANCHOR: OUTER_END ===\n"
    )

    def test_outer_block_survives_nested_inner_anchor(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "nested.ts", self.NESTED)
        blocks = extract_anchor_blocks(p)
        assert set(blocks) == {"OUTER", "OUTER_INNER"}
        assert blocks["OUTER_INNER"] == "const inner = 2;"
        assert "const before = 1;" in blocks["OUTER"]
        assert "const after = 3;" in blocks["OUTER"]

    def test_blocks_agree_with_index_and_line_ranges(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "nested.ts", self.NESTED)
        assert set(extract_anchor_blocks(p)) == set(extract_anchors(p))
        assert set(extract_anchor_blocks(p)) == set(extract_anchor_line_ranges(p))

    def test_flat_anchors_unchanged(self, tmp_path: Path) -> None:
        text = (
            "// === ANCHOR: FIRST_START ===\n"
            "const a = 1;\n"
            "// === ANCHOR: FIRST_END ===\n"
            "const between = 0;\n"
            "// === ANCHOR: SECOND_START ===\n"
            "const b = 2;\n"
            "// === ANCHOR: SECOND_END ===\n"
        )
        p = _write(tmp_path, "flat.ts", text)
        assert extract_anchor_blocks(p) == {
            "FIRST": "const a = 1;",
            "SECOND": "const b = 2;",
        }

    def test_dangling_start_is_not_returned(self, tmp_path: Path) -> None:
        text = (
            "// === ANCHOR: GOOD_START ===\n"
            "const ok = 1;\n"
            "// === ANCHOR: GOOD_END ===\n"
            "// === ANCHOR: DANGLING_START ===\n"
            "const oops = 2;\n"
        )
        p = _write(tmp_path, "dangling.ts", text)
        assert set(extract_anchor_blocks(p)) == {"GOOD"}


class TestBug6NameContainingStartEnd:
    """이름 자체에 START/END 가 들어간 앵커 (`VIB_START_CMD`, `..._EXCLUSIVE_END`).

    `([A-Z0-9_]+)_START` 부분 매칭으로 판별하면 END 마커인
    `VIB_START_CMD_END` 가 이름 `VIB` 의 START 로 오인되어 블록이 닫히지 않는다.
    토큰 전체를 잡고 접미사로 판별해야 한다.
    """

    def test_name_containing_start_is_parsed(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: VIB_START_CMD_START ===\n"
            "run = 1\n"
            "# === ANCHOR: VIB_START_CMD_END ===\n"
        )
        p = _write(tmp_path, "vib_start_cmd.py", text)
        assert extract_anchors(p) == ["VIB_START_CMD"]
        assert extract_anchor_blocks(p) == {"VIB_START_CMD": "run = 1"}
        assert set(extract_anchor_line_ranges(p)) == {"VIB_START_CMD"}

    def test_name_ending_with_end_is_parsed(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: HEAD_EXCLUSIVE_END_START ===\n"
            "value = 2\n"
            "# === ANCHOR: HEAD_EXCLUSIVE_END_END ===\n"
        )
        p = _write(tmp_path, "chunk.py", text)
        assert extract_anchors(p) == ["HEAD_EXCLUSIVE_END"]
        assert extract_anchor_blocks(p) == {"HEAD_EXCLUSIVE_END": "value = 2"}

    def test_blocks_agree_with_index_for_start_named_anchors(
        self, tmp_path: Path
    ) -> None:
        text = (
            "// === ANCHOR: ONBOARDING_START ===\n"
            "const a = 1;\n"
            "// === ANCHOR: ONBOARDING_STARTWSLINSTALL_START ===\n"
            "const b = 2;\n"
            "// === ANCHOR: ONBOARDING_STARTWSLINSTALL_END ===\n"
            "// === ANCHOR: ONBOARDING_END ===\n"
        )
        p = _write(tmp_path, "onboarding.ts", text)
        assert set(extract_anchor_blocks(p)) == set(extract_anchors(p))


class TestSignatureExtraction:
    def test_python_def_signature(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: MY_FUNC_START ===\n"
            "def my_func(a: int, b: str) -> bool:\n"
            "    return True\n"
            "# === ANCHOR: MY_FUNC_END ===\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        assert len(spans) == 1
        assert spans[0]["signature"] == "def my_func(a: int, b: str) -> bool:"

    def test_python_class_signature(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: MY_CLASS_START ===\n"
            "class MyClass(BaseModel):\n"
            "    pass\n"
            "# === ANCHOR: MY_CLASS_END ===\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        assert spans[0]["signature"] == "class MyClass(BaseModel):"

    def test_js_function_signature(self, tmp_path: Path) -> None:
        text = (
            "// === ANCHOR: HANDLER_START ===\n"
            "export async function handleRequest(req, res) {\n"
            "  return res.json({});\n"
            "}\n"
            "// === ANCHOR: HANDLER_END ===\n"
        )
        p = _write(tmp_path, "handler.ts", text)
        spans = extract_anchor_spans(p)
        assert spans[0]["signature"] == "export async function handleRequest(req, res) {"

    def test_const_arrow_signature(self, tmp_path: Path) -> None:
        text = (
            "// === ANCHOR: COMP_START ===\n"
            "const MyComponent = () => {\n"
            "  return <div/>;\n"
            "};\n"
            "// === ANCHOR: COMP_END ===\n"
        )
        p = _write(tmp_path, "comp.tsx", text)
        spans = extract_anchor_spans(p)
        assert spans[0]["signature"] == "const MyComponent = () => {"

    def test_no_signature_for_config_block(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: CONFIG_START ===\n"
            "MAX_RETRIES = 3\n"
            "TIMEOUT = 30\n"
            "# === ANCHOR: CONFIG_END ===\n"
        )
        p = _write(tmp_path, "config.py", text)
        spans = extract_anchor_spans(p)
        assert "signature" not in spans[0]

    def test_signature_within_5_lines(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: DELAYED_START ===\n"
            "# some comment\n"
            "# another comment\n"
            "# yet another\n"
            "def delayed_func():\n"
            "    pass\n"
            "# === ANCHOR: DELAYED_END ===\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        assert spans[0]["signature"] == "def delayed_func():"

    def test_signature_beyond_5_lines_not_found(self, tmp_path: Path) -> None:
        text = (
            "# === ANCHOR: FAR_START ===\n"
            "# 1\n"
            "# 2\n"
            "# 3\n"
            "# 4\n"
            "# 5\n"
            "def too_far():\n"
            "    pass\n"
            "# === ANCHOR: FAR_END ===\n"
        )
        p = _write(tmp_path, "mod.py", text)
        spans = extract_anchor_spans(p)
        assert "signature" not in spans[0]

