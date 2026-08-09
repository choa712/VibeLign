# === ANCHOR: META_PATHS_START ===
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetaPaths:
    root: Path

    @property
    def vibelign_dir(self) -> Path:
        return self.root / ".vibelign"

    @property
    def config_path(self) -> Path:
        return self.vibelign_dir / "config.yaml"

    @property
    def project_map_path(self) -> Path:
        return self.vibelign_dir / "project_map.json"

    @property
    def state_path(self) -> Path:
        return self.vibelign_dir / "state.json"

    @property
    def anchor_index_path(self) -> Path:
        return self.vibelign_dir / "anchor_index.json"

    @property
    def anchor_meta_path(self) -> Path:
        return self.vibelign_dir / "anchor_meta.json"

    @property
    def checkpoints_dir(self) -> Path:
        return self.vibelign_dir / "checkpoints"

    @property
    def plans_dir(self) -> Path:
        return self.vibelign_dir / "plans"

    @property
    def reports_dir(self) -> Path:
        return self.vibelign_dir / "reports"

    @property
    def logs_dir(self) -> Path:
        return self.vibelign_dir / "logs"

    @property
    def watch_state_path(self) -> Path:
        return self.vibelign_dir / "watch_state.json"

    @property
    def watch_log_path(self) -> Path:
        return self.vibelign_dir / "watch.log"

    @property
    def work_memory_path(self) -> Path:
        return self.vibelign_dir / "work_memory.json"

    @property
    def handoff_path(self) -> Path:
        """Session Handoff 원본 데이터 (issue #6).

        PROJECT_CONTEXT.md 안에 끼워 두면 재생성 때마다 경계를 다시 찾아야
        하는데, 신뢰할 수 없는 자유 텍스트를 생성 문서 안에서 in-band 구분자로
        감싸는 방식은 구분자가 무엇이든 위조된다(경계 추론 3종이 모두 깨졌다).
        원본을 밖에 두면 경계 파싱이 아예 사라지고 PROJECT_CONTEXT.md 는
        순수 생성물이 된다.
        """
        return self.vibelign_dir / "handoff.json"

    @property
    def context_lock_path(self) -> Path:
        return self.vibelign_dir / "project_context.lock"

    @property
    def scan_cache_path(self) -> Path:
        return self.vibelign_dir / "scan_cache.json"

    @property
    def analysis_cache_path(self) -> Path:
        return self.vibelign_dir / "analysis_cache.json"

    @property
    def ui_label_index_path(self) -> Path:
        return self.vibelign_dir / "ui_label_index.json"

    @property
    def docs_visual_dir(self) -> Path:
        return self.vibelign_dir / "docs_visual"

    def docs_visual_path(self, source_relative_path: str, *, is_extra: bool = False) -> Path:
        rel = Path(source_relative_path.replace("\\", "/"))
        base = self.docs_visual_dir / "_extra" if is_extra else self.docs_visual_dir
        return base / Path(f"{rel.as_posix()}.json")

    @property
    def docs_html_dir(self) -> Path:
        return self.vibelign_dir / "docs_html"

    def docs_html_path(self, source_relative_path: str, *, is_extra: bool = False) -> Path:
        rel = Path(source_relative_path.replace("\\", "/"))
        base = self.docs_html_dir / "_extra" if is_extra else self.docs_html_dir
        return base / Path(f"{rel.as_posix()}.json")

    @property
    def docs_index_path(self) -> Path:
        return self.vibelign_dir / "docs_index.json"

    @property
    def doc_sources_path(self) -> Path:
        return self.vibelign_dir / "doc_sources.json"

    def ensure_vibelign_dirs(self) -> None:
        self.vibelign_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.docs_visual_dir.mkdir(parents=True, exist_ok=True)
        self.docs_html_dir.mkdir(parents=True, exist_ok=True)

    def ensure_vibelign_dir(self) -> None:
        self.vibelign_dir.mkdir(parents=True, exist_ok=True)

    def report_path(self, command: str, fmt: str) -> Path:
        suffix = ".json" if fmt == "json" else ".md"
        return self.reports_dir / f"{command}_latest{suffix}"


# === ANCHOR: META_PATHS_END ===
