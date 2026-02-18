"""Domain models — what the TUI works with."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Board:
    id: str
    name: str
    columns: list[Column] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)


@dataclass
class Column:
    id: str
    title: str
    type: str
    settings: str = ""


@dataclass
class Group:
    id: str
    title: str
    color: str = ""


@dataclass
class BoardItem:
    id: str
    name: str
    status_label: str = ""
    status_color: str = ""
    assignees: list[str] = field(default_factory=list)
    assignee_ids: list[str] = field(default_factory=list)
    update_count: int = 0
    column_values: dict[str, str] = field(default_factory=dict)
    # column_values maps column title -> display text


@dataclass
class ItemDetail:
    id: str
    name: str
    board_name: str = ""
    group_title: str = ""
    created_at: str = ""
    updated_at: str = ""
    column_values: dict[str, str] = field(default_factory=dict)
    updates: list[Update] = field(default_factory=list)


@dataclass
class Update:
    id: str
    text: str
    author: str = ""
    created_at: str = ""
    like_count: int = 0
    liker_ids: list[str] = field(default_factory=list)
    replies: list[Update] = field(default_factory=list)

    def is_liked_by(self, user_id: str) -> bool:
        return user_id in self.liker_ids


@dataclass
class User:
    id: str
    name: str
    email: str = ""
