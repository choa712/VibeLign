# === ANCHOR: ATOMIC_WRITE_START ===
"""생성물 파일을 원자적으로 교체한다 (issue #2).

`path.write_text()` 는 파일을 먼저 비우고 쓴다. 그 사이에 크래시가 나거나
다른 프로세스가 읽으면 잘린 파일이 남거나 읽힌다. PROJECT_CONTEXT.md 처럼
AI 가 세션 시작에 읽는 파일이 반쯤 잘려 있으면, 그 세션은 잘못된 상태를
사실로 믿고 작업을 시작한다.

같은 디렉터리에 임시 파일로 쓴 뒤 os.replace 로 갈아끼운다. 읽는 쪽은
항상 옛 내용 아니면 새 내용이고, 그 중간은 없다.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


# === ANCHOR: ATOMIC_WRITE_ATOMIC_WRITE_TEXT_START ===
def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """텍스트를 원자적으로 교체 저장한다.

    임시 파일은 반드시 대상과 같은 디렉터리에 만든다. os.replace 는 같은
    파일시스템 안에서만 원자적이라, /tmp 를 거치면 보장이 깨진다.
    """
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    # mkstemp 는 0600 으로 만든다. 그대로 교체하면 write_text 로 만들어졌던
    # 파일(보통 0644)이 소유자 전용으로 바뀐다 — 팀 공유 체크아웃이나
    # 다른 사용자로 도는 도구가 갑자기 읽지 못하게 된다.
    try:
        keep_mode: int | None = path.stat().st_mode & 0o777
    except OSError:
        keep_mode = None
    fd, tmp_name = tempfile.mkstemp(
        dir=str(directory), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        # newline 은 기본값 그대로 둔다 — Path.write_text 와 줄바꿈 처리가
        # 달라지면 Windows 에서 기존 파일과 diff 가 통째로 뜬다.
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            _ = handle.write(text)
            handle.flush()
            # fsync 없이 replace 하면 전원이 끊길 때 빈 파일이 남을 수 있다
            # (교체는 기록됐는데 내용은 아직 디스크에 없는 상태).
            os.fsync(handle.fileno())
        # 새로 만드는 경우 0644 — write_text 가 umask 022 에서 내던 값과 같다.
        # umask 를 읽으려면 잠시 바꿔야 하는데(os.umask), 그 사이 다른 스레드가
        # 파일을 만들면 권한이 틀어지므로 고정값을 쓴다.
        os.chmod(tmp_path, keep_mode if keep_mode is not None else 0o644)
        os.replace(tmp_path, path)
    except BaseException:
        with _suppress_os_error():
            tmp_path.unlink()
        raise


# === ANCHOR: ATOMIC_WRITE_ATOMIC_WRITE_TEXT_END ===


# === ANCHOR: ATOMIC_WRITE__SUPPRESS_OS_ERROR_START ===
@contextmanager
def _suppress_os_error() -> Iterator[None]:
    try:
        yield
    except OSError:
        pass


# === ANCHOR: ATOMIC_WRITE__SUPPRESS_OS_ERROR_END ===


# === ANCHOR: ATOMIC_WRITE_FILE_LOCK_START ===
@contextmanager
def file_lock(lock_path: Path, *, timeout: float = 10.0) -> Iterator[bool]:
    """생성물 재생성을 직렬화하는 권고적(advisory) 잠금.

    권고적이라는 뜻: 이 함수를 쓰지 않는 쓰기는 막지 못한다. 파손 방지의
    본체는 atomic_write_text 이고, 이 잠금은 "동시에 두 번 재생성해서 나중
    것이 먼저 것을 덮는" 순서 뒤집힘을 줄인다.

    잠금을 얻지 못해도 예외를 던지지 않고 False 를 내주며 진행한다 —
    잠금 실패로 체크포인트 저장 자체가 막히는 편이 더 나쁘다.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle: BinaryIO | None = None
    acquired = False
    try:
        handle = open(lock_path, "a+b")
    except OSError:
        handle = None
    if handle is not None:
        try:
            acquired = _try_lock(handle, timeout)
        except OSError:
            acquired = False
    # yield 는 정확히 한 번. 이 자리를 try/except OSError 로 감싸면 with 본문이
    # 던진 OSError(디스크 가득참·권한)가 여기로 되돌아와 두 번째 yield 를
    # 실행하고, 원래 오류가 "generator didn't stop after throw()" 로 뒤바뀐다.
    # 잠금 획득 실패는 위에서 이미 삼켰고, 본문 예외는 그대로 올려보낸다.
    try:
        yield acquired
    finally:
        if handle is not None:
            if acquired:
                with _suppress_os_error():
                    _unlock(handle)
            with _suppress_os_error():
                handle.close()


def _try_lock(handle: BinaryIO, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if _lock_once(handle):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _lock_once(handle: BinaryIO) -> bool:
    if sys.platform == "win32":
        try:
            import msvcrt

            _ = handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (OSError, ImportError, ValueError):
            return False
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, ImportError, ValueError):
        return False


def _unlock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        _ = handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# === ANCHOR: ATOMIC_WRITE_FILE_LOCK_END ===
# === ANCHOR: ATOMIC_WRITE_END ===
