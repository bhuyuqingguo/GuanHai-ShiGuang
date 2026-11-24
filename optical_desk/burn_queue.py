from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class BurnEntry:
    """刻录队列中的虚拟节点；删除和移动绝不修改电脑上的原文件。"""

    name: str
    source: Path | None
    is_dir: bool
    parent: "BurnEntry | None" = field(default=None, repr=False)
    children: list["BurnEntry"] = field(default_factory=list)
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)

    def is_descendant_of(self, other: "BurnEntry") -> bool:
        current = self.parent
        while current:
            if current is other:
                return True
            current = current.parent
        return False

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class BurnQueue:
    def __init__(self):
        self.roots: list[BurnEntry] = []

    @staticmethod
    def from_path(path: Path, parent: BurnEntry | None = None) -> BurnEntry:
        path = path.expanduser().resolve()
        entry = BurnEntry(path.name, path, path.is_dir(), parent)
        if entry.is_dir:
            try:
                children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
            except OSError:
                children = []
            entry.children = [BurnQueue.from_path(child, entry) for child in children]
        return entry

    @staticmethod
    def _siblings(parent: BurnEntry | None, roots: list[BurnEntry]) -> list[BurnEntry]:
        return parent.children if parent else roots

    def _has_name(self, name: str, parent: BurnEntry | None, ignore: set[int] | None = None) -> bool:
        ignored = ignore or set()
        return any(id(entry) not in ignored and entry.name.casefold() == name.casefold()
                   for entry in self._siblings(parent, self.roots))

    def add_paths(self, paths: Iterable[str | Path], parent: BurnEntry | None = None) -> int:
        added = 0
        for value in paths:
            path = Path(value)
            if not path.exists() or self._has_name(path.name, parent):
                continue
            entry = self.from_path(path, parent)
            self._siblings(parent, self.roots).append(entry)
            added += 1
        return added

    def contains(self, target: BurnEntry) -> bool:
        return any(entry is target for root in self.roots for entry in root.walk())

    def remove(self, entries: Iterable[BurnEntry]) -> int:
        selected = set(map(id, entries))
        removed = 0
        for entry in list(entries):
            if id(entry) not in selected or not self.contains(entry):
                continue
            siblings = self._siblings(entry.parent, self.roots)
            siblings.remove(entry)
            entry.parent = None
            removed += 1
        return removed

    def move(self, entries: Iterable[BurnEntry], parent: BurnEntry | None) -> int:
        selected = list(entries)
        ids = set(map(id, selected))
        if parent and any(parent is entry or parent.is_descendant_of(entry) for entry in selected):
            return 0
        if any(self._has_name(entry.name, parent, ids) for entry in selected):
            return 0
        if all(entry.parent is parent for entry in selected):
            return 0
        for entry in selected:
            self._siblings(entry.parent, self.roots).remove(entry)
        for entry in selected:
            entry.parent = parent
            self._siblings(parent, self.roots).append(entry)
        return len(selected)

    def all_entries(self):
        for root in self.roots:
            yield from root.walk()

    def materialize(self, destination: str | Path) -> int:
        """按虚拟树生成刻录暂存目录；优先硬链接，失败时复制。"""
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        count = 0

        def write_entry(entry: BurnEntry, target: Path):
            nonlocal count
            if entry.is_dir:
                target.mkdir(parents=True, exist_ok=True)
                for child in entry.children:
                    write_entry(child, target / child.name)
                if entry.source:
                    shutil.copystat(entry.source, target, follow_symlinks=True)
            else:
                if not entry.source or not entry.source.is_file():
                    raise OSError(f"源文件不存在：{entry.source or entry.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(entry.source, target)
                except OSError:
                    shutil.copy2(entry.source, target)
                count += 1

        for root in self.roots:
            write_entry(root, destination / root.name)
        return count
