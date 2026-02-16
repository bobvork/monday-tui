"""Transform API models to domain models."""

from __future__ import annotations

from mui.api.models import ApiBoard, ApiColumnValue, ApiItem, ApiUpdate, ApiUser
from mui.models import Board, BoardItem, Column, Group, ItemDetail, Update, User


def map_board(api: ApiBoard) -> Board:
    return Board(
        id=api.id,
        name=api.name,
        columns=[Column(id=c.id, title=c.title, type=c.type, settings=c.settings) for c in api.columns],
        groups=[Group(id=g.id, title=g.title, color=g.color) for g in api.groups],
    )


def map_board_item(api: ApiItem, user_lookup: dict[str, str] | None = None) -> BoardItem:
    user_lookup = user_lookup or {}
    status_label = ""
    assignees: list[str] = []
    col_values: dict[str, str] = {}

    for cv in api.column_values:
        display = cv.text or ""
        col_title = cv.column_title or cv.id

        if cv.type == "status" and not status_label:
            status_label = cv.label or cv.text or ""

        if cv.type == "people" and cv.persons_and_teams:
            names = [user_lookup.get(str(p["id"]), f"User {p['id']}") for p in cv.persons_and_teams]
            assignees = names
            display = ", ".join(names)

        if display:
            col_values[col_title] = display

    return BoardItem(
        id=api.id,
        name=api.name,
        status_label=status_label,
        assignees=assignees,
        column_values=col_values,
    )


def map_item_detail(api: ApiItem, user_lookup: dict[str, str] | None = None) -> ItemDetail:
    user_lookup = user_lookup or {}
    col_values: dict[str, str] = {}
    for cv in api.column_values:
        title = cv.column_title or cv.id
        display = cv.text or ""
        if cv.type == "people" and cv.persons_and_teams:
            display = ", ".join(
                user_lookup.get(str(p["id"]), f"User {p['id']}") for p in cv.persons_and_teams
            )
        if display:
            col_values[title] = display

    return ItemDetail(
        id=api.id,
        name=api.name,
        board_name=api.board_name,
        group_title=api.group_title,
        created_at=api.created_at,
        updated_at=api.updated_at,
        column_values=col_values,
        updates=[_map_update(u, user_lookup) for u in api.updates],
    )


def _map_update(api: ApiUpdate, user_lookup: dict[str, str]) -> Update:
    return Update(
        id=api.id,
        text=api.text_body,
        author=user_lookup.get(api.creator_id, api.creator_name or f"User {api.creator_id}"),
        created_at=api.created_at,
        like_count=len(api.likes),
        replies=[_map_update(r, user_lookup) for r in api.replies],
    )


def map_user(api: ApiUser) -> User:
    return User(id=api.id, name=api.name, email=api.email)
