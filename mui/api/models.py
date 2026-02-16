"""API response dataclasses — mirrors the Monday.com GraphQL response shape."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ApiBoard:
    id: str
    name: str
    columns: list[ApiColumn] = field(default_factory=list)
    groups: list[ApiGroup] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ApiBoard:
        return cls(
            id=str(d["id"]),
            name=d["name"],
            columns=[ApiColumn.from_dict(c) for c in d.get("columns", [])],
            groups=[ApiGroup.from_dict(g) for g in d.get("groups", [])],
        )


@dataclass
class ApiColumn:
    id: str
    title: str
    type: str
    settings: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ApiColumn:
        return cls(
            id=d["id"],
            title=d["title"],
            type=d["type"],
            settings=d.get("settings", ""),
        )


@dataclass
class ApiGroup:
    id: str
    title: str
    color: str = ""
    position: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ApiGroup:
        return cls(
            id=d["id"],
            title=d["title"],
            color=d.get("color", ""),
            position=d.get("position", ""),
        )


@dataclass
class ApiColumnValue:
    id: str
    type: str
    text: str | None = None
    value: str | None = None
    label: str | None = None  # StatusValue
    persons_and_teams: list[dict] | None = None  # PeopleValue
    column_title: str | None = None  # from column { title }

    @classmethod
    def from_dict(cls, d: dict) -> ApiColumnValue:
        col = d.get("column")
        return cls(
            id=d["id"],
            type=d["type"],
            text=d.get("text"),
            value=d.get("value"),
            label=d.get("label"),
            persons_and_teams=d.get("persons_and_teams"),
            column_title=col["title"] if col else None,
        )


@dataclass
class ApiItem:
    id: str
    name: str
    created_at: str = ""
    updated_at: str = ""
    group_id: str = ""
    group_title: str = ""
    board_id: str = ""
    board_name: str = ""
    column_values: list[ApiColumnValue] = field(default_factory=list)
    updates: list[ApiUpdate] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ApiItem:
        group = d.get("group") or {}
        board = d.get("board") or {}
        return cls(
            id=str(d["id"]),
            name=d["name"],
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            group_id=group.get("id", ""),
            group_title=group.get("title", ""),
            board_id=str(board.get("id", "")),
            board_name=board.get("name", ""),
            column_values=[ApiColumnValue.from_dict(cv) for cv in d.get("column_values", [])],
            updates=[ApiUpdate.from_dict(u) for u in d.get("updates", [])],
        )


@dataclass
class ApiUpdate:
    id: str
    text_body: str = ""
    created_at: str = ""
    creator_id: str = ""
    creator_name: str = ""
    replies: list[ApiUpdate] = field(default_factory=list)
    likes: list[ApiLike] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ApiUpdate:
        creator = d.get("creator") or {}
        return cls(
            id=str(d["id"]),
            text_body=d.get("text_body", ""),
            created_at=d.get("created_at", ""),
            creator_id=str(creator.get("id", "")),
            creator_name=creator.get("name", ""),
            replies=[ApiUpdate.from_dict(r) for r in d.get("replies", [])],
            likes=[ApiLike.from_dict(lk) for lk in d.get("likes", [])],
        )


@dataclass
class ApiLike:
    id: str
    creator_id: str

    @classmethod
    def from_dict(cls, d: dict) -> ApiLike:
        return cls(id=str(d["id"]), creator_id=str(d["creator_id"]))


@dataclass
class ApiUser:
    id: str
    name: str
    email: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ApiUser:
        return cls(id=str(d["id"]), name=d["name"], email=d.get("email", ""))
