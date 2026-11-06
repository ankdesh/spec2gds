"""Filesystem capabilities for one hosted Spec root.

Walk directories through descriptors with O_NOFOLLOW. Reads and publication use
the held parent descriptor, so replacing a checked path with a link cannot turn
a service request into access outside the configured tree.
"""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4


class SpecFilesystem:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Spec root must be a directory.")

    def path(self, value: str | Path, *, spec: bool = False) -> Path:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        # Reject traversal before normalizing it, including traversal back into
        # the root. Do not resolve child links before checking the components.
        if ".." in candidate.parts:
            raise ValueError("Paths must stay within the Spec root.")
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Paths must stay within the Spec root.") from exc
        if spec and (candidate.suffix.lower() != ".spec" or not relative.parts):
            raise ValueError("Select a regular .spec file within the Spec root.")
        with self.directory(relative.parent) as descriptor:
            try:
                info = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None and (stat.S_ISLNK(info.st_mode) or (spec and not stat.S_ISREG(info.st_mode))):
                raise ValueError("Symbolic links and non-regular Spec files are not allowed.")
        return candidate

    @contextmanager
    def directory(self, relative: str | Path = ".") -> Iterator[int]:
        parts = Path(relative).parts
        if Path(relative).is_absolute() or ".." in parts:
            raise ValueError("Paths must stay within the Spec root.")
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            yield descriptor
        finally:
            os.close(descriptor)

    def read(self, value: str | Path, *, spec: bool = True) -> bytes:
        path = self.path(value, spec=spec)
        with self.directory(path.parent.relative_to(self.root)) as parent:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("Select a regular .spec file.")
                return stream.read()

    def publish(self, value: str | Path, data: bytes, *, replace: bool = False, spec: bool = True) -> None:
        path = self.path(value, spec=spec)
        with self.directory(path.parent.relative_to(self.root)) as parent:
            temporary = f".{path.name}.{uuid4().hex}.stage"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if replace:
                    os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
                else:
                    os.link(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass

    def listing(self, value: str | None = None) -> dict:
        path = self.path(value or self.root)
        relative = path.relative_to(self.root)
        directories, specifications = [], []
        with self.directory(relative) as descriptor:
            for entry in sorted(os.scandir(descriptor), key=lambda item: item.name.casefold()):
                if entry.is_symlink():
                    continue
                item = {"name": entry.name, "path": str(path / entry.name)}
                if entry.is_dir(follow_symlinks=False):
                    if entry.name != ".spec2gds" and not entry.name.endswith(".spec.artifacts"):
                        directories.append(item)
                elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".spec"):
                    specifications.append(item)
        return {"path": str(path), "parent": None if path == self.root else str(path.parent),
                "home": str(self.root), "roots": [str(self.root)], "root": str(self.root),
                "separator": os.sep, "directories": directories, "specifications": specifications}

    def ensure_directory(self, value: str | Path) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        relative = candidate.relative_to(self.root)
        if ".." in relative.parts:
            raise ValueError("Paths must stay within the Spec root.")
        for index, part in enumerate(relative.parts):
            with self.directory(Path(*relative.parts[:index])) as parent:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(child)
        return candidate

    def mkdir(self, parent: str, name: str) -> dict:
        path = self.path(parent)
        with self.directory(path.relative_to(self.root)) as descriptor:
            os.mkdir(name, dir_fd=descriptor)
        return self.listing(str(path / name))
