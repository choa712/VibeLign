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

import errno
import os
import secrets
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


# === ANCHOR: ATOMIC_WRITE_ATOMIC_WRITE_TEXT_START ===
def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """텍스트를 원자적으로 교체 저장한다."""
    target = resolve_write_target(path)
    staged = stage_text(target, text, encoding=encoding)
    commit_staged([(staged, target)])


class PartialCommitError(OSError):
    """일부만 교체된 채 실패했다. 아무것도 안 바뀐 것과 구별해야 한다.

    호출자가 이걸 그냥 "저장 중단" 으로 보고하면 사용자는 원래 상태가
    그대로라고 믿는다. 실제로는 정본만 새것이라 다음 재생성이 파생물을
    맞춰줘야 한다 — 그 사실을 알려야 다시 실행할 수 있다.
    """

    def __init__(self, replaced: list[Path], remaining: list[Path], cause: BaseException):
        self.replaced = replaced
        self.remaining = remaining
        landed = ", ".join(p.name for p in replaced)
        missed = ", ".join(p.name for p in remaining)
        super().__init__(
            f"일부만 반영됐습니다 — 갱신됨: {landed} / 갱신 못함: {missed} ({cause}). "
            "정본이 먼저 갱신되므로 같은 명령을 다시 실행하면 나머지가 맞춰집니다."
        )


def commit_staged(pairs: list[tuple[Path, Path]]) -> None:
    """준비된 임시 파일들을 연달아 교체한다.

    두 파일을 한꺼번에 원자적으로 바꾸는 건 저널 없이는 불가능하다. 대신
    "내용 만들기·쓰기·fsync" 를 전부 끝낸 뒤 os.replace 만 연속 실행해,
    둘이 어긋나 있는 창을 실질적으로 없앤다 (사이에 I/O 가 없다).

    PROJECT_CONTEXT.md 와 handoff.json 처럼 짝으로 읽히는 파일에 쓴다 —
    하나만 갱신된 채 끝나면 새 AI 가 서로 다른 세션을 가리키는 두 파일을 읽는다.
    중간에 끊길 수 있으므로 호출자가 **정본을 먼저, 파생물을 나중에** 배치해야
    한다. 그래야 끊겼을 때 다음 재생성이 파생물을 다시 만들어 자가 복구된다.

    첫 교체가 성공한 뒤 실패하면 PartialCommitError 를 던진다 — 아무것도
    안 바뀐 실패와 섞이면 호출자가 사용자에게 거짓말을 하게 된다.
    """
    replaced: list[Path] = []
    try:
        for index, (tmp_path, dest) in enumerate(pairs):
            try:
                os.replace(tmp_path, dest)
            except OSError as exc:
                if replaced:
                    raise PartialCommitError(
                        replaced, [d for _t, d in pairs[index:]], exc
                    ) from exc
                raise
            replaced.append(dest)
    finally:
        for tmp_path, _dest in pairs:
            if tmp_path.exists():
                with _suppress_os_error():
                    tmp_path.unlink()


def stage_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """교체 직전 상태까지 준비하고 임시 파일 경로를 돌려준다.

    임시 파일은 반드시 대상과 같은 디렉터리에 만든다. os.replace 는 같은
    파일시스템 안에서만 원자적이라, /tmp 를 거치면 보장이 깨진다.
    """
    # 호출자가 resolve_write_target 을 거쳤다고 가정하지 않는다 — 여기서
    # 한 번 더 해석해도 결과는 같고(멱등), 빠뜨렸을 때 링크를 깨뜨리지 않는다.
    path = resolve_write_target(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    # 기존 파일이면 그 권한을 그대로 유지한다. mkstemp 의 0600 으로 덮으면
    # write_text 로 만들어졌던 파일(보통 0644)이 소유자 전용으로 바뀌어,
    # 공유 체크아웃에서 남이 읽지 못하게 된다.
    try:
        keep_mode: int | None = path.stat().st_mode & 0o777
    except OSError:
        keep_mode = None
    fd, tmp_path = _open_exclusive(directory, path.name, keep_mode)
    try:
        # newline 은 기본값 그대로 둔다 — Path.write_text 와 줄바꿈 처리가
        # 달라지면 Windows 에서 기존 파일과 diff 가 통째로 뜬다.
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            _ = handle.write(text)
            handle.flush()
            # fsync 없이 replace 하면 전원이 끊길 때 빈 파일이 남을 수 있다
            # (교체는 기록됐는데 내용은 아직 디스크에 없는 상태).
            os.fsync(handle.fileno())
    except BaseException:
        with _suppress_os_error():
            tmp_path.unlink()
        raise
    return tmp_path


# === ANCHOR: ATOMIC_WRITE_ATOMIC_WRITE_TEXT_END ===


# === ANCHOR: ATOMIC_WRITE_RESOLVE_WRITE_TARGET_START ===
def resolve_write_target(path: Path) -> Path:
    """실제로 갈아끼울 경로. 심볼릭 링크면 그 최종 대상.

    os.replace 는 링크 자체를 일반 파일로 바꿔버린다. AGENTS.md 처럼 공유
    정책을 링크로 걸어둔 설정이 조용히 끊기므로, 링크를 따라가는
    write_text 의 동작에 맞춘다.

    끊긴 링크(대상 없음)도 대상 경로를 돌려준다 — write_text 가 그 자리에
    파일을 만드는 동작과 같다. 링크 루프면 resolve 가 OSError 를 던지고,
    그건 그대로 올려보낸다 (조용히 링크를 덮어쓰는 것보다 낫다).

    여러 파일을 짝으로 교체할 때는 **호출자가 먼저 이 함수를 거친 경로를**
    commit_staged 에 넘겨야 한다. stage_text 만 해석하고 원래 경로로
    replace 하면 링크가 그대로 깨진다.
    """
    if not path.is_symlink():
        return path
    return path.resolve()


# === ANCHOR: ATOMIC_WRITE_RESOLVE_WRITE_TARGET_END ===


# === ANCHOR: ATOMIC_WRITE__OPEN_EXCLUSIVE_START ===
def _open_exclusive(
    directory: Path, base_name: str, keep_mode: int | None
) -> tuple[int, Path]:
    """임시 파일을 배타 생성하고 (fd, 경로) 를 돌려준다.

    mkstemp 를 쓰지 않는 이유: mkstemp 는 항상 0600 으로 만든다. 신규 파일에
    고정 권한을 부여하면(0644 등) umask 077 로 운영하는 환경에서 handoff 내용이
    같은 머신의 다른 사용자에게 노출된다. os.open 에 0o666 을 넘기면 커널이
    umask 를 적용하므로, open()·write_text 와 정확히 같은 권한이 나온다.
    os.umask 를 읽었다 되돌리는 방식은 그 사이 다른 스레드가 만드는 파일의
    권한을 망가뜨리므로 쓰지 않는다.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for _ in range(100):
        candidate = directory / f".{base_name}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(candidate, flags, keep_mode if keep_mode is not None else 0o666)
        except FileExistsError:
            continue
        if keep_mode is not None:
            # O_CREAT 모드에도 umask 가 적용되므로, 기존 권한을 그대로
            # 이어받으려면 명시적으로 다시 지정해야 한다.
            os.fchmod(fd, keep_mode)
        return fd, candidate
    raise OSError(f"{directory} 에 임시 파일을 만들지 못했습니다")


# === ANCHOR: ATOMIC_WRITE__OPEN_EXCLUSIVE_END ===


# === ANCHOR: ATOMIC_WRITE__SUPPRESS_OS_ERROR_START ===
@contextmanager
def _suppress_os_error() -> Iterator[None]:
    try:
        yield
    except OSError:
        pass


# === ANCHOR: ATOMIC_WRITE__SUPPRESS_OS_ERROR_END ===


# === ANCHOR: ATOMIC_WRITE__WARN_UNSERIALIZED_START ===
_warned_unserialized = False


def _warn_unserialized(reason: str) -> None:
    """직렬화 없이 진행한다는 사실을 한 번은 알린다.

    조용히 넘어가면 사용자는 보호가 걸려 있다고 믿는다. 여기서 막지 않는
    이유는 그 환경에서 도구 자체를 못 쓰게 되기 때문이고, 그렇다면 최소한
    보이게는 해야 한다. 세션당 한 번만 — 매 쓰기마다 찍으면 소음이 된다.
    """
    global _warned_unserialized
    if _warned_unserialized:
        return
    _warned_unserialized = True
    print(
        f"⚠️  VibeLign: 파일 잠금 없이 진행합니다 — {reason}. "
        "여러 세션이 동시에 쓰면 PROJECT_CONTEXT.md 와 handoff.json 이 "
        "어긋날 수 있습니다.",
        file=sys.stderr,
    )


# === ANCHOR: ATOMIC_WRITE__WARN_UNSERIALIZED_END ===


# === ANCHOR: ATOMIC_WRITE_FILE_LOCK_START ===
@contextmanager
def file_lock(lock_path: Path, *, timeout: float = 10.0) -> Iterator[bool]:
    """생성물 재생성을 직렬화하는 권고적(advisory) 잠금.

    권고적이라는 뜻: 이 함수를 쓰지 않는 쓰기는 막지 못한다. 파손 방지의
    본체는 atomic_write_text 이고, 이 잠금은 "동시에 두 번 재생성해서 나중
    것이 먼저 것을 덮는" 순서 뒤집힘을 막는다.

    두 가지 실패를 구분한다:

    - **잠금을 지원하지 않는 환경**(flock 없는 파일시스템 등) → False 를
      내주고 진행한다. 더 할 수 있는 게 없고, 여기서 막으면 그런 환경에서는
      도구 자체를 못 쓴다.
    - **다른 프로세스가 쥐고 있어 timeout 초과** → TimeoutError 를 던진다.
      그대로 진행하면 두 세션의 handoff.json 과 PROJECT_CONTEXT.md 가 섞여,
      새 AI 가 읽는 두 파일이 서로 다른 세션을 가리키게 된다.
      (TimeoutError 는 OSError 하위라 기존 호출부의 except OSError 가 받는다)
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle: BinaryIO | None = None
    acquired = False
    try:
        handle = open(lock_path, "a+b")
    except OSError as exc:
        handle = None
        _warn_unserialized(f"잠금 파일을 열 수 없습니다 ({exc})")
    if handle is not None:
        outcome = _try_lock(handle, timeout)
        if outcome == "contended":
            with _suppress_os_error():
                handle.close()
            raise TimeoutError(
                f"{lock_path} 잠금을 {timeout:g}초 안에 얻지 못했습니다 — "
                "다른 VibeLign 작업이 같은 파일을 쓰는 중입니다. "
                "섞인 상태를 남기지 않으려고 중단합니다."
            )
        acquired = outcome == "acquired"
        if not acquired:
            _warn_unserialized("이 파일시스템이 잠금을 지원하지 않습니다")
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


def _try_lock(handle: BinaryIO, timeout: float) -> str:
    """acquired / contended / unsupported 중 하나를 돌려준다.

    셋을 구분하는 이유: "다른 프로세스가 쥐고 있다"와 "이 파일시스템이 잠금을
    지원하지 않는다"는 대응이 정반대다. 전자는 멈춰야 하고 후자는 진행해야 한다.
    """
    deadline = time.monotonic() + timeout
    while True:
        outcome = _lock_once(handle)
        if outcome is None:
            return "unsupported"
        if outcome:
            return "acquired"
        if time.monotonic() >= deadline:
            return "contended"
        time.sleep(0.05)


def _lock_once(handle: BinaryIO) -> bool | None:
    """True=획득, False=경합 중, None=이 환경이 잠금을 지원하지 않음."""
    if sys.platform == "win32":
        try:
            import msvcrt
        except ImportError:
            return None
        try:
            _ = handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            # EACCES/EDEADLOCK 은 경합, 그 밖(ENOSYS 등)은 미지원으로 본다.
            return False if exc.errno in (errno.EACCES, errno.EDEADLK) else None
        except ValueError:
            return None
    try:
        import fcntl
    except ImportError:
        return None
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        return False if exc.errno in (errno.EACCES, errno.EAGAIN) else None
    except ValueError:
        return None


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
