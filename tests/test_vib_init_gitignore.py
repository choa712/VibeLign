import tempfile
import unittest
from pathlib import Path

# _ensure_gitignore_entry 는 vib_init_cmd 에서 vib_start_cmd 로 옮겨졌다
# (프로젝트 세팅 담당이 init → start 로 바뀌면서). 임포트가 따라가지 않아
# 이 파일 하나 때문에 pytest 전체 수집이 중단됐다.
from vibelign.commands.vib_start_cmd import _ensure_gitignore_entry


class VibInitGitignoreTest(unittest.TestCase):
    def test_init_ensures_checkpoints_gitignore_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _ensure_gitignore_entry(root)
            text = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".vibelign/checkpoints/", text)


if __name__ == "__main__":
    unittest.main()
