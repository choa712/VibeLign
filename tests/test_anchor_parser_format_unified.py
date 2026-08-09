"""정본 앵커 형식을 모든 파서가 동일하게 인식하는지 검증한다.

파서마다 형식이 갈라지면 "어느 경로로 읽었는가"에 따라 앵커 집합이 달라진다.
실제로 rg 가속 경로(fast_tools)는 느슨한 형식도 인식해, ripgrep 설치 여부에
따라 vib anchor --auto 대상 파일이 바뀌는 결함이 있었다. fast_tools 모듈
docstring 의 "기능 차이는 없고 속도 차이만 있다" 계약 위반이었다.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from vibelign.core import anchor_tools, fast_tools
from vibelign.core.anchor_tools import (
    extract_anchor_blocks,
    extract_anchor_line_ranges,
    extract_anchor_spans,
    extract_anchors,
)
from vibelign.core.structure_policy import ANCHOR_MARKER_PATTERN


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


MIXED = (
    "// ANCHOR: LEGACY_ONE_START\n"
    "const legacy = 1;\n"
    "// ANCHOR: LEGACY_ONE_END\n"
    "// === ANCHOR: CANONICAL_START ===\n"
    "const canonical = 2;\n"
    "// === ANCHOR: CANONICAL_END ===\n"
)


def test_all_parsers_agree_on_mixed_file(tmp_path: Path) -> None:
    p = _write(tmp_path, "mixed.ts", MIXED)
    expected = {"CANONICAL"}
    assert set(extract_anchors(p)) == expected
    assert set(extract_anchor_blocks(p)) == expected
    assert set(extract_anchor_line_ranges(p)) == expected
    assert {s["name"] for s in extract_anchor_spans(p)} == expected


def test_blocks_reject_phantom_mention_in_comment(tmp_path: Path) -> None:
    """주석 속 언급은 앵커가 아니다 (TestBug2 의 blocks 판)."""
    text = (
        "# format: /abs/path/file.py:ANCHOR: PHANTOM_START\n"
        "# === ANCHOR: REAL_START ===\n"
        "x = 1\n"
        "# === ANCHOR: REAL_END ===\n"
    )
    p = _write(tmp_path, "phantom.py", text)
    assert set(extract_anchor_blocks(p)) == {"REAL"}
    assert extract_anchor_blocks(p)["REAL"] == "x = 1"


def test_both_parsers_share_the_canonical_pattern() -> None:
    assert anchor_tools.ANCHOR_RE.pattern == ANCHOR_MARKER_PATTERN
    assert fast_tools._ANCHOR_RE.pattern == ANCHOR_MARKER_PATTERN


class TestRgPathMatchesPythonPath(unittest.TestCase):
    def test_rg_command_uses_canonical_pattern(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["rg"], returncode=0, stdout="", stderr=""
        )
        with patch.object(fast_tools, "_RG", "rg"):
            with patch(
                "vibelign.core.fast_tools.subprocess.run", return_value=completed
            ) as run:
                _ = fast_tools.grep_anchors_rg(Path("/tmp/project"))
        cmd = cast("list[str]", run.call_args.args[0])
        self.assertIn(ANCHOR_MARKER_PATTERN, cmd)

    def test_rg_command_requests_nul_separator(self) -> None:
        """경로/매치 구분자는 NUL 이어야 한다 (Windows 드라이브 문자 대비)."""
        completed = subprocess.CompletedProcess(
            args=["rg"], returncode=0, stdout="", stderr=""
        )
        with patch.object(fast_tools, "_RG", "rg"):
            with patch(
                "vibelign.core.fast_tools.subprocess.run", return_value=completed
            ) as run:
                _ = fast_tools.grep_anchors_rg(Path("/tmp/project"))
        cmd = cast("list[str]", run.call_args.args[0])
        self.assertIn("--null", cmd)

    def _run_with_stdout(self, stdout: str, root: str) -> dict[str, list[str]] | None:
        completed = subprocess.CompletedProcess(
            args=["rg"], returncode=0, stdout=stdout, stderr=""
        )
        with patch.object(fast_tools, "_RG", "rg"):
            with patch(
                "vibelign.core.fast_tools.subprocess.run", return_value=completed
            ):
                return fast_tools.grep_anchors_rg(Path(root))

    def test_rg_output_parsing_matches_extract_anchors(self) -> None:
        """rg -o 출력(정본 마커 줄 전체)에서 extract_anchors 와 같은 이름을 뽑는다."""
        stdout = (
            "/tmp/project/mod.py\0# === ANCHOR: FOO_START ===\n"
            "/tmp/project/mod.py\0# === ANCHOR: FOO_END ===\n"
            "/tmp/project/mod.py\0# === ANCHOR: __INIT___START ===\n"
            "/tmp/project/mod.py\0# === ANCHOR: __INIT___END ===\n"
        )
        result = self._run_with_stdout(stdout, "/tmp/project")
        self.assertEqual(result, {"mod.py": ["FOO", "__INIT__"]})

    def test_rg_output_parsing_handles_indented_marker(self) -> None:
        """들여쓴 마커는 -o 출력에 선행 공백이 포함된 채로 온다."""
        stdout = "/tmp/project/mod.py\0    # === ANCHOR: INNER_START ===\n"
        result = self._run_with_stdout(stdout, "/tmp/project")
        self.assertEqual(result, {"mod.py": ["INNER"]})

    def test_rg_output_parsing_handles_windows_drive_letter(self) -> None:
        """C:\\... 경로에서 드라이브 문자의 ':' 가 구분자로 오인되면 안 된다.

        ':' 로 나누던 시절엔 모든 앵커가 파일 "C" 하나에 몰렸다.
        """
        stdout = "C:\\proj\\mod.py\0# === ANCHOR: WIN_START ===\n"
        result = self._run_with_stdout(stdout, "C:\\proj")
        assert result is not None
        self.assertEqual(list(result.values()), [["WIN"]])
        self.assertNotIn("C", result)

    def test_rg_output_ignores_legacy_format(self) -> None:
        """구 형식은 rg 패턴에 걸리지 않으므로 인덱스에 들어가면 안 된다."""
        stdout = "/tmp/project/mod.py\0# ANCHOR: LEGACY_START\n"
        result = self._run_with_stdout(stdout, "/tmp/project")
        self.assertEqual(result, {})

    def test_rg_output_ignores_marker_embedded_in_code(self) -> None:
        """줄 안쪽에 박힌 마커는 rg 파싱 단계에서도 앵커가 아니다."""
        stdout = '/tmp/project/mod.py\0s = "# === ANCHOR: PHANTOM_START ==="\n'
        result = self._run_with_stdout(stdout, "/tmp/project")
        self.assertEqual(result, {})
