import errno
import glob
import hashlib
import os
import platform
import struct
import sys
import threading
import typing as t
from importlib import metadata
from pathlib import Path

from .metadata import (
    EntryPointsResolver,
    MetadataEntryPointsResolver,
    build_entry_point_index,
    parse_entry_points_text,
    serialize_entry_points_text,
)


def get_user_cache_dir() -> Path:
    """
    Returns the path of the user's cache dir (e.g., ~/.cache on Linux, or ~/Library/Caches on Mac).

    :return: a Path pointing to the platform-specific cache dir of the user
    """

    if "windows" == platform.system().lower():
        return Path(os.path.expandvars(r"%LOCALAPPDATA%\cache"))
    if "darwin" == platform.system().lower():
        return Path.home() / "Library" / "Caches"
    if "linux" == platform.system().lower():
        string_path = os.environ.get("XDG_CACHE_HOME")
        if string_path and os.path.isabs(string_path):
            return Path(string_path)

    # Use the common place to store caches in Linux as a default
    return Path.home() / ".cache"


def _get_mtime(path: str) -> float:
    try:
        s = os.stat(path)
        return s.st_mtime
    except OSError as err:
        if err.errno not in {errno.ENOENT, errno.ENOTDIR}:
            raise
    return -1.0


def _float_to_bytes(f: float) -> bytes:
    return struct.Struct("f").pack(f)


class EntryPointsCache(EntryPointsResolver):
    """
    Special ``EntryPointsResolver`` that uses ``importlib.metadata`` and a file system cache. The basic and
    hash key calculation idea is taken from stevedore, but entry point parsing/serializing is simplified
    slightly. Instead of writing json files, that includes metadata, we instead write one giant
    ``entry_points.txt`` compatible file.

    You can get a singleton instance via ``EntryPointsCache.instance()`` that also keeps an in-memory cache
    for the current ``sys.path``.
    """

    _instance: "EntryPointsCache" = None
    _instance_lock: threading.RLock = threading.RLock()

    _cache: t.Dict[t.Tuple[str, ...], t.Dict[str, t.List[metadata.EntryPoint]]]
    """For each specific path (like sys.path), we store a dict of group -> [entry point]."""

    def __init__(self):
        self._lock = threading.RLock()
        self._cache = {}
        self._resolver = MetadataEntryPointsResolver()
        self._cache_dir = get_user_cache_dir() / "plux"

    def get_entry_points(self) -> t.Dict[str, t.List[metadata.EntryPoint]]:
        """
        Returns a dictionary of entry points for the current ``sys.path``.
        """
        path = sys.path
        key = tuple(path)

        try:
            return self._cache[key]
        except KeyError:
            pass

        # build the cache within a lock context. there's a potential race condition here when sys.path is
        # altered concurrently, but we consider this an unsupported fringe case.
        with self._lock:
            if key not in self._cache:
                # we don't need to pass the sys.path here, since it's used implicitly when calling
                # ``metadata.distributions()`` in ``resolve_entry_points``.
                self._cache[key] = self._build_and_store_index(self._cache_dir)

            return self._cache[key]

    def _build_and_store_index(self, cache_dir: Path) -> t.Dict[str, t.List[metadata.EntryPoint]]:
        # first, try and load the index from the file system
        path_key = self._calculate_hash_key(sys.path)

        file_cache = cache_dir / f"{path_key}.entry_points.txt"

        if file_cache.exists():
            return build_entry_point_index(parse_entry_points_text(file_cache.read_text()))

        # if it doesn't exist, create the index from the current path
        index = self._resolver.get_entry_points()

        # store it to disk
        if not file_cache.parent.exists():
            file_cache.parent.mkdir(parents=True, exist_ok=True)
        file_cache.write_text(serialize_entry_points_text(index))

        return index

    def _calculate_hash_key(self, path: t.List[str]):
        """
        Calculates a hash of all modified times of all ``entry_point.txt`` files in the path. Basic idea
        taken from ``stevedore._cache._hash_settings_for_path``. The main difference to it is that it also
        considers entry points files linked through ``entry_points_editable.txt``.

        The hash considers:
        * the path executable (python version)
        * the path prefix (like a .venv path)
        * mtime of each path entry
        * mtimes of all entry_point.txt files within the path
        * mtimes of all entry_point.txt files linked through entry_points_editable.txt files

        :param path: the path (typically ``sys.path``)
        :return: a sha256 hash that hashes the path's entry point state
        """
        h = hashlib.sha256()

        # Tie the cache to the python interpreter, in case it is part of a
        # virtualenv.
        h.update(sys.executable.encode("utf-8"))
        h.update(sys.prefix.encode("utf-8"))

        for entry in path:
            mtime = _get_mtime(entry)
            h.update(entry.encode("utf-8"))
            h.update(_float_to_bytes(mtime))

            for ep_file in self._iter_entry_point_files(entry):
                mtime = _get_mtime(ep_file)
                h.update(ep_file.encode("utf-8"))
                h.update(_float_to_bytes(mtime))

        return h.hexdigest()

    def _iter_entry_point_files(self, entry: str):
        """
        An iterator that returns all entry_point.txt file paths in the given path entry. It transparently
        resolves editable entry points links.

        :param entry: a path entry like ``/home/user/myproject/.venv/lib/python3.11/site-packages``
        """
        yield from glob.iglob(os.path.join(entry, "*.dist-info", "entry_points.txt"))
        yield from glob.iglob(os.path.join(entry, "*.egg-info", "entry_points.txt"))

        # resolve editable links
        for item in glob.iglob(os.path.join(entry, "*.dist-info", "entry_points_editable.txt")):
            with open(item, "r") as fd:
                link = fd.read()
                if os.path.exists(link):
                    yield link

    @staticmethod
    def instance() -> "EntryPointsCache":
        if EntryPointsCache._instance:
            return EntryPointsCache._instance

        with EntryPointsCache._instance_lock:
            if EntryPointsCache._instance:
                return EntryPointsCache._instance

            EntryPointsCache._instance = EntryPointsCache()
            return EntryPointsCache._instance
