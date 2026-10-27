"""原件哈希缓存。每次检查文件身份，最终导出可强制重读字节。"""
from collections import OrderedDict
import hashlib
import logging
from pathlib import Path
import threading
import time
from weakref import WeakValueDictionary

_lock = threading.RLock()
_cache = OrderedDict()
_file_locks = WeakValueDictionary()
_MAX_ENTRIES = 512
log = logging.getLogger(__name__)


def source_signature(path):
    path = Path(path).resolve()
    stat = path.stat()
    return (str(path), stat.st_size, stat.st_mtime_ns)


def source_sha256(path, *, force=False):
    # 同一文件并发读取合并；读取期间文件变化时拒绝缓存不稳定内容。
    with _lock:
        name = str(Path(path).resolve())
        file_lock = _file_locks.get(name)
        if file_lock is None:
            file_lock = threading.RLock()
            _file_locks[name] = file_lock
    with file_lock:
        key = source_signature(path)
        with _lock:
            if not force and key in _cache:
                _cache.move_to_end(key)
                log.info("source_hash cache=hit bytes=%s", key[1])
                return _cache[key]
        started = time.perf_counter()
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if source_signature(path) != key:
            raise OSError("来源在校验期间发生变化")
        # 同路径只保留最新指纹，避免文件换版累积缓存。
        result = digest.hexdigest()
        with _lock:
            for old in list(_cache):
                if old[0] == key[0]:
                    del _cache[old]
            _cache[key] = result
            while len(_cache) > _MAX_ENTRIES:
                _cache.popitem(last=False)
        log.info("source_hash cache=miss forced=%s bytes=%s duration_ms=%.2f", force, key[1], (time.perf_counter()-started)*1000)
        return result
