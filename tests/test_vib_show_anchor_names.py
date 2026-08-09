"""vib show 의 앵커 이름 해석 회귀 테스트.

이름 자체에 `_END` 가 들어가거나 언더스코어로 끝나는 앵커
(`HEAD_EXCLUSIVE_END`, `__INIT__`)를 곧바로 정규화하면 영영 조회할 수 없다.
정확 일치를 먼저 시도하고, 마커 이름(`FOO_START`)은 폴백으로 해석한다.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from vibelign.commands.vib_show_cmd import run_vib_show


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".vibelign").mkdir()
    (tmp_path / "chunk.py").write_text(
        "# === ANCHOR: HEAD_EXCLUSIVE_END_START ===\n"
        "LIMIT = 3\n"
        "# === ANCHOR: HEAD_EXCLUSIVE_END_END ===\n"
        "\n"
        "# === ANCHOR: __INIT___START ===\n"
        "VERSION = 1\n"
        "# === ANCHOR: __INIT___END ===\n"
        "\n"
        "# === ANCHOR: PLAIN_START ===\n"
        "PLAIN = 2\n"
        "# === ANCHOR: PLAIN_END ===\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _show(anchor: str, capsys: pytest.CaptureFixture[str]) -> str:
    run_vib_show(Namespace(file="chunk.py", anchor=anchor))
    return capsys.readouterr().out


def test_name_ending_with_end_is_found(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _show("HEAD_EXCLUSIVE_END", capsys)
    assert "찾을 수 없어요" not in out
    assert "LIMIT = 3" in out
    assert "HEAD_EXCLUSIVE_END" in out


def test_dunder_name_is_found(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _show("__INIT__", capsys)
    assert "찾을 수 없어요" not in out
    assert "VERSION = 1" in out


def test_marker_name_falls_back(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """기존 편의 동작: 마커 이름으로 요청해도 해석된다."""
    out = _show("PLAIN_START", capsys)
    assert "찾을 수 없어요" not in out
    assert "PLAIN = 2" in out
    assert "앵커: PLAIN" in out


def test_exact_match_path_renders_header(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """정확 일치 경로에서도 헤더가 렌더링돼야 한다 (UnboundLocalError 회귀)."""
    out = _show("PLAIN", capsys)
    assert "chunk.py:" in out
    assert "앵커: PLAIN" in out


def test_unknown_anchor_lists_available(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _show("NOPE", capsys)
    assert "찾을 수 없어요" in out
    assert "사용 가능한 앵커" in out
