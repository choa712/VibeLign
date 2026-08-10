# === ANCHOR: TEST_WAIVED_RISK_BLOB_PINNING_START ===
"""waiver 가 걸린 파일이 바뀌면 알아채야 한다 (적대 리뷰 HIGH).

merge-gate 의 accepted_risks 는 리뷰어가 쓴 **제목 문자열**에 정규식을 걸 뿐,
커밋이나 hunk 지문에 묶을 수단이 없다. 그래서 waiver 가 살아 있는 동안
그 파일에 새 악성 변경이 들어와도 비슷한 제목이면 함께 통과할 수 있다.

게이트 쪽에서 못 하는 결속을 리포 쪽에서 건다: waiver 를 발급할 때 검토한
그 내용 그대로인지 해시로 확인한다. 파일이 바뀌면 이 테스트가 깨지고,
waiver 의 전제("검토한 그 기존 결함")를 다시 따져보게 된다.

파일을 정당하게 고쳤다면 아래 두 가지 중 하나를 해야 한다:
  1) 이슈 #8 을 해결했다면 waiver 를 지우고 이 테스트도 지운다
  2) 다른 이유로 고쳤다면 새 내용을 사람이 검토한 뒤 해시를 갱신한다
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

WAIVED_FILE = Path("vibelign-gui/src-tauri/src/commands/tool_install.rs")

# 2026-08-10 검토 시점의 내용. `vib` 앵커 주석만 있는 상태이며 설치 로직은
# origin/main 과 동일하다. 갱신하려면 위 독스트링의 절차를 따를 것.
REVIEWED_SHA256 = "eca31cc76c39502d160d42b3bf173d52d159fe5064dd3f79487a0a8cba889f69"

WAIVER_FILE = Path(".claude/branch-flow.yml")
WAIVER_ID = "tool-install-remote-shell-exec"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _waiver_is_active() -> bool:
    path = _repo_root() / WAIVER_FILE
    if not path.exists():
        return False
    return WAIVER_ID in path.read_text(encoding="utf-8")


# === ANCHOR: TEST_WAIVED_RISK_BLOB_PINNING_TESTBLOBPINNING_START ===
class TestBlobPinning:
    def test_waived_file_matches_the_reviewed_content(self) -> None:
        if not _waiver_is_active():
            return  # waiver 를 지웠으면 결속도 필요 없다
        target = _repo_root() / WAIVED_FILE
        assert target.exists(), f"{WAIVED_FILE} 이 없습니다 — waiver 를 정리하세요"
        actual = _sha256(target)
        assert actual == REVIEWED_SHA256, (
            f"{WAIVED_FILE} 가 waiver 발급 시점과 다릅니다.\n"
            f"  검토됨: {REVIEWED_SHA256}\n"
            f"  현재:   {actual}\n"
            "waiver 는 '검토한 그 기존 결함' 에만 유효합니다. 이 파일을 고쳤다면 "
            "이슈 #8 해결 여부에 따라 waiver 를 지우거나, 새 내용을 사람이 검토한 뒤 "
            "REVIEWED_SHA256 을 갱신하세요."
        )

    def test_waiver_has_an_expiry(self) -> None:
        if not _waiver_is_active():
            return
        text = (_repo_root() / WAIVER_FILE).read_text(encoding="utf-8")
        match = re.search(r'expires:\s*"(\d{4}-\d{2}-\d{2})"', text)
        assert match, "waiver 에 만료일이 없습니다 — 무기한 수용 금지"

    def test_waiver_is_not_file_wide(self) -> None:
        """파일 전체를 수용하면 그 파일의 새 결함까지 통과한다."""
        if not _waiver_is_active():
            return
        text = (_repo_root() / WAIVER_FILE).read_text(encoding="utf-8")
        match = re.search(r'match:\s*"([^"]+)"', text)
        assert match, "waiver 에 match 패턴이 없습니다"
        pattern = match.group(1)
        assert pattern.strip() != "tool_install\\\\.rs", (
            "match 가 파일 전체입니다 — 그 파일의 다른 종류 결함까지 수용됩니다"
        )


# === ANCHOR: TEST_WAIVED_RISK_BLOB_PINNING_TESTBLOBPINNING_END ===
# === ANCHOR: TEST_WAIVED_RISK_BLOB_PINNING_END ===
