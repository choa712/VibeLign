# === ANCHOR: STRUCTURE_POLICY_START ===
from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from vibelign.core.meta_paths import MetaPaths

COMMON_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "target",
        ".next",
        ".pnpm-store",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".sisyphus",
        ".Trash",
        "Library",
        "CloudStorage",
    }
)

WINDOWS_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# 앵커 마커의 정본 형식. 등호 3개로 감싼 마커만 앵커로 인정한다.
# (형식 예시를 주석에 그대로 적으면 그 줄이 팬텀 앵커로 잡히므로 쓰지 않는다.)
# 여기 한 곳에만 두는 이유: 파서마다 따로 정의하면 형식이 갈라져
# "어떤 경로로 읽었는가"에 따라 앵커 집합이 달라진다. 실제로 rg 가속
# 경로(fast_tools)와 Python 경로(anchor_tools)가 갈라져 ripgrep 설치
# 여부에 따라 `vib anchor --auto` 대상이 바뀌는 결함이 있었다.
# rg 는 -o 로 매치 전체를 출력하므로 같은 패턴 문자열을 그대로 쓴다.
# 공백은 같은 줄 안에서만 허용한다(\s 는 개행도 먹는다). Python 은 전문
# 검색(finditer), ripgrep 과 마커 파서는 줄 단위라, 개행을 허용하면 줄을
# 넘겨 쓴 마커가 경로마다 다르게 인식돼 인덱스·span·block 이 어긋난다.
#
# 줄 단위로 고정한다: "줄 전체가 마커인 주석"만 경계로 인정한다. 고정하지
# 않으면 소스 텍스트 안에 박힌 마커 모양 문자열이 진짜 경계가 돼 블록이
# 의도보다 짧게 잘리고 바깥 구간이 보호 없이 남는다 — 게다가 START/END
# 쌍은 맞아 보이므로 validate 가 조용히 통과한다. 이 리포에서만 테스트
# 파일의 문자열 리터럴 776건이 그렇게 팬텀 앵커로 잡히고 있었다.
# 끝의 \r 은 CRLF 체크아웃(Windows)용 — 없으면 그쪽에서 전부 인식 실패한다.
# 쓰는 쪽은 re.MULTILINE 을 반드시 켜야 한다(^/$ 가 줄 단위여야 함).
# rg 는 줄 지향이라 플래그 없이 그대로 동작한다.
ANCHOR_MARKER_PATTERN = (
    r"^[ \t]*(?://|#)[ \t]*===[ \t]*ANCHOR:[ \t]*([A-Z0-9_]+)[ \t]*===[ \t\r]*$"
)

_ANCHOR_MARKER_RE = re.compile(ANCHOR_MARKER_PATTERN, re.MULTILINE)


def has_anchor_markers(text: str) -> bool:
    """정본 형식 앵커 마커가 하나라도 있는가.

    "앵커가 있는가" 판정이 모듈마다 제각각(부분 문자열 검사, 느슨한 정규식)이면
    같은 파일이 어느 경로로 보느냐에 따라 보호됨/안 됨으로 갈린다. 실제로
    preview_anchor_targets 는 `"=== ANCHOR:" in text` 부분 문자열로 판정해,
    문자열 리터럴에 마커를 적어둔 테스트 파일 14개를 "이미 앵커가 있다"고 보고
    영영 대상에서 제외했다 — 그 파일들은 보호 없이 남아 있었다.

    짝이 맞는 START/END 가 최소 한 쌍 있어야 참이다. 방향 없는 `ANCHOR: FOO`
    나 END 만 있는 `ANCHOR: FAKE_END` 는 block/range 파서가 경계로 쓰지 못한다.
    그런 걸 참으로 보면 precheck·guard 는 통과시키는데 실제 보호 구간은
    0인 상태가 된다 — 정확히 이 규칙군이 막으려는 침묵이다.

    패턴을 소유한 이 모듈에 둔다. 상위 모듈(anchor_tools)에 두면
    watch_rules·risk_analyzer 가 쓰려 할 때 순환 임포트가 된다.
    """
    if not text:
        return False
    opened: set[str] = set()
    closed: set[str] = set()
    for match in _ANCHOR_MARKER_RE.finditer(text):
        raw = match.group(1)
        if raw.endswith("_START"):
            name = raw[: -len("_START")]
            if name in closed:
                return True
            opened.add(name)
        elif raw.endswith("_END"):
            name = raw[: -len("_END")]
            if name in opened:
                return True
            closed.add(name)
    return False

GENERATED_ARTIFACT_DIR_NAMES: frozenset[str] = frozenset(
    {"dist", "build", "target", ".next", ".pnpm-store", "node_modules"}
)

SOURCE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".cpp",
        ".c",
        ".hpp",
        ".h",
    }
)

CORE_ENTRY_FILE_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "app.py",
        "cli.py",
        "server.py",
        "index.js",
        "app.js",
        "main.js",
        "main.ts",
        "index.ts",
        "main.rs",
        "main.go",
        "main.cpp",
        "Program.cs",
        "vib_cli.py",
        "mcp_server.py",
    }
)

SCAN_EXTRA_IGNORED: frozenset[str] = frozenset(
    {
        "docs",
        "tests",
        ".github",
        ".vibelign",
        ".claude",
        ".codex",
        ".agents",
        ".omo",
        ".omc",
    }
)
SCAN_IGNORED_DIRS: frozenset[str] = COMMON_IGNORED_DIRS | SCAN_EXTRA_IGNORED
SCAN_IGNORED_DIRS_LOWER: frozenset[str] = frozenset(
    name.lower() for name in SCAN_IGNORED_DIRS
)

CHECKPOINT_EXTRA_IGNORED: frozenset[str] = frozenset()
CHECKPOINT_EXTRA_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        "db_maintenance_backups",
        # 에이전트 worktree / 외부 도구 상태 / 빌드 산출물은 gitignore·scan 에서도
        # 제외되는 재생성 가능 폴더라 체크포인트가 매번 복사하면 백업이 수 GB 로 비대해진다.
        ".claude",
        ".codex",
        ".agents",
        ".omo",
        ".omc",
        "dist-vib",
    }
)
CHECKPOINT_IGNORED_DIRS: frozenset[str] = (
    COMMON_IGNORED_DIRS | CHECKPOINT_EXTRA_IGNORED | CHECKPOINT_EXTRA_IGNORED_DIRS
)
CHECKPOINT_IGNORED_DIRS_LOWER: frozenset[str] = frozenset(
    name.lower() for name in CHECKPOINT_IGNORED_DIRS
)

TRANSFER_EXTRA_IGNORED: frozenset[str] = frozenset({".vibelign"})
TRANSFER_TREE_IGNORED_DIRS: frozenset[str] = (
    COMMON_IGNORED_DIRS | TRANSFER_EXTRA_IGNORED
)
TRANSFER_TREE_IGNORED_DIRS_LOWER: frozenset[str] = frozenset(
    name.lower() for name in TRANSFER_TREE_IGNORED_DIRS
)

CHECKPOINT_IGNORED_FILES: frozenset[str] = frozenset(
    {
        "VIBELIGN_PATCH_REQUEST.md",
        "VIBELIGN_EXPLAIN.md",
        "VIBELIGN_GUARD.md",
        "VIBELIGN_ASK.md",
        "anchor_meta.json",
        "project_map.json",
        "state.json",
        "watch_state.json",
        "watch.log",
        "scan_cache.json",
        "analysis_cache.json",
        "ui_label_index.json",
        "vibelign.db",
        "vibelign.db-wal",
        "vibelign.db-shm",
        "engine.pid",
        "engine.sock",
        "engine.log",
    }
)

HANDOFF_SKIP_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dylib",
        ".dll",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".ico",
        ".zip",
        ".tar",
        ".gz",
        ".lock",
        ".egg-info",
    }
)

HANDOFF_KEY_FILE_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "app.py",
        "index.py",
        "server.py",
        "index.js",
        "app.js",
        "main.js",
        "index.ts",
        "app.ts",
        "main.ts",
        "main.go",
        "main.rs",
        "Main.java",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
    }
)

HANDOFF_SKIP_PREFIXES: tuple[str, ...] = (".vibelign", ".git", "__pycache__")

STRUCTURE_PATH_PREFIXES: tuple[str, ...] = (
    "vibelign/core/",
    "vibelign/commands/",
    "vibelign/mcp/",
    "vibelign/service/",
    "vibelign/patch/",
)

_DEFAULT_SMALL_FIX_THRESHOLD = 30

SOURCE_FILE_SUFFIXES: tuple[str, ...] = tuple(
    sorted(ext.lstrip(".") for ext in SOURCE_FILE_EXTENSIONS)
)


# === ANCHOR: STRUCTURE_POLICY_NORMALIZE_IGNORED_NAMES_START ===
def normalize_ignored_names(names: Iterable[str]) -> frozenset[str]:
    return frozenset(name.lower() for name in names)


# === ANCHOR: STRUCTURE_POLICY_NORMALIZE_IGNORED_NAMES_END ===


# === ANCHOR: STRUCTURE_POLICY_HAS_IGNORED_PART_START ===
def has_ignored_part(
    parts: tuple[str, ...],
    ignored: Iterable[str] = SCAN_IGNORED_DIRS_LOWER,
    # === ANCHOR: STRUCTURE_POLICY_HAS_IGNORED_PART_END ===
) -> bool:
    ignored_lower = (
        ignored if isinstance(ignored, frozenset) else normalize_ignored_names(ignored)
    )
    return any(part.lower() in ignored_lower for part in parts)


# === ANCHOR: STRUCTURE_POLICY_IS_SOURCE_FILE_START ===
def is_source_file(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_FILE_EXTENSIONS


# === ANCHOR: STRUCTURE_POLICY_IS_SOURCE_FILE_END ===


# === ANCHOR: STRUCTURE_POLICY_IS_CORE_ENTRY_FILE_START ===
def is_core_entry_file(path: Path | str) -> bool:
    name = path if isinstance(path, str) else path.name
    return name in CORE_ENTRY_FILE_NAMES


# === ANCHOR: STRUCTURE_POLICY_IS_CORE_ENTRY_FILE_END ===


# === ANCHOR: STRUCTURE_POLICY_IS_GENERATED_ARTIFACT_PATH_START ===
def is_generated_artifact_path(path: Path | tuple[str, ...] | str) -> bool:
    if isinstance(path, Path):
        parts = path.parts
    elif isinstance(path, tuple):
        parts = path
    else:
        parts = tuple(path.replace("\\", "/").split("/"))
    return any(part.lower() in GENERATED_ARTIFACT_DIR_NAMES for part in parts)


# === ANCHOR: STRUCTURE_POLICY_IS_GENERATED_ARTIFACT_PATH_END ===


# === ANCHOR: STRUCTURE_POLICY_SHOULD_INCLUDE_VIBELIGN_FILE_START ===
def should_include_vibelign_file(filename: str) -> bool:
    return filename not in CHECKPOINT_IGNORED_FILES


# === ANCHOR: STRUCTURE_POLICY_SHOULD_INCLUDE_VIBELIGN_FILE_END ===


# === ANCHOR: STRUCTURE_POLICY_IS_TRIVIAL_PACKAGE_INIT_START ===
def is_trivial_package_init(path: Path, text: str) -> bool:
    if path.name != "__init__.py":
        return False

    stripped = text.strip()
    if not stripped:
        return True

    try:
        body = ast.parse(text).body
    except SyntaxError:
        return False

    for node in body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target_names: list[str] = []
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        target_names.append(target.id)
            elif isinstance(node.target, ast.Name):
                target_names.append(node.target.id)
            if target_names and all(name == "__all__" for name in target_names):
                continue
        return False
    return True


# === ANCHOR: STRUCTURE_POLICY_IS_TRIVIAL_PACKAGE_INIT_END ===


# === ANCHOR: STRUCTURE_POLICY_CLASSIFY_STRUCTURE_PATH_START ===
def classify_structure_path(rel_path: str) -> str:
    low = rel_path.lower()
    if low.startswith(".vibelign/"):
        return "meta"
    if low.startswith("docs/") or low.endswith(".md"):
        return "docs"
    if low.startswith("tests/") or "/tests/" in low or low.startswith("test_"):
        return "tests"
    if low in {"pyproject.toml", "package.json", "package-lock.json", "uv.lock"}:
        return "config"
    if (
        low.startswith(".claude/")
        or low.startswith(".github/")
        or low.endswith(".yaml")
        or low.endswith(".yml")
        or low.endswith(".toml")
    ):
        return "config"
    if low.startswith(STRUCTURE_PATH_PREFIXES):
        return "production"
    if low.endswith(".py"):
        return "non_vibelign_production"
    return "support"


# === ANCHOR: STRUCTURE_POLICY_CLASSIFY_STRUCTURE_PATH_END ===


# === ANCHOR: STRUCTURE_POLICY_IS_STRUCTURE_PRODUCTION_KIND_START ===
def is_structure_production_kind(path_kind: str) -> bool:
    return path_kind == "production"


# === ANCHOR: STRUCTURE_POLICY_IS_STRUCTURE_PRODUCTION_KIND_END ===


# === ANCHOR: STRUCTURE_POLICY_SMALL_FIX_LINE_THRESHOLD_START ===
def small_fix_line_threshold(meta: MetaPaths) -> int:
    if not meta.config_path.exists():
        return _DEFAULT_SMALL_FIX_THRESHOLD
    try:
        content = meta.config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _DEFAULT_SMALL_FIX_THRESHOLD
    match = re.search(r"^small_fix_line_threshold:\s*(\d+)\s*$", content, re.MULTILINE)
    if not match:
        return _DEFAULT_SMALL_FIX_THRESHOLD
    return int(match.group(1))


# === ANCHOR: STRUCTURE_POLICY_SMALL_FIX_LINE_THRESHOLD_END ===
# === ANCHOR: STRUCTURE_POLICY_END ===
