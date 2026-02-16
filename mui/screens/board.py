"""Board view screen — main working environment."""

from __future__ import annotations

import json
import webbrowser
from typing import Any

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, Static

from mui import keybindings as kb
from mui.api.client import MondayClient
from mui.api.models import ApiBoard, ApiColumnValue, ApiItem
from mui.api import queries
from mui import cache
from mui.mappers import map_board, map_board_item
from mui.models import Board, BoardItem


# Columns we always show (in order) plus any extra visible columns
STATUS_TYPES = {"status", "color"}
PEOPLE_TYPES = {"people", "multiple-person"}
SKIP_TYPES = {
    "name",
    "subtasks",
    "auto_number",
    "file",
    "board_relation",
    "mirror",
    "formula",
}

# Status label → (short name, font color, background color)
STATUS_DISPLAY: dict[str, tuple[str, str, str]] = {
    "done": ("Done", "dark_green", "pale_green3"),
    "ready 4 test": ("Test", "navy_blue", "light_sky_blue1"),
    "work in progress": ("WiP", "orange4", "khaki1"),
    "working on it": ("WiP", "orange4", "khaki1"),
    "blocked": ("Block", "dark_red", "indian_red1"),
    "backlog": ("-", "grey23", "grey70"),
    "stuck": ("Stuck", "dark_red", "indian_red1"),
    "meer info nodig": ("?", "dark_red", "indian_red1"),
}

MY_USER_STYLE = "bold cyan"
MATCH_HIGHLIGHT_STYLE = "bold yellow"


def _shorten_name(name: str) -> str:
    """'Bob Vork' → 'Bob v', 'john@crowdaboutnow.nl' → 'john'."""
    if "@" in name:
        return name.split("@")[0]
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}"
    return name


class BoardScreen(Screen):
    """Displays items for one group at a time with a sticky group header."""

    BINDINGS = [
        Binding(kb.PREV_GROUP[0], "prev_group", "[ Prev", show=True),
        Binding(kb.NEXT_GROUP[0], "next_group", "] Next", show=True),
        Binding(
            kb.SEARCH_ITEMS[0], "start_search", "/ Search", show=True, priority=True
        ),
        Binding(kb.NEXT_MATCH[0], "next_match", "n Next Match", show=False),
        Binding(kb.PREV_MATCH[0], "prev_match", "N Prev Match", show=False),
        Binding(kb.SWITCH_BOARD[0], "switch_board", "^P Board", show=True),
        Binding(kb.EDIT_TITLE[0], "edit_title", "i Edit", show=True),
        Binding(kb.CHANGE_STATUS[0], "change_status", "s Status", show=True),
        Binding(kb.CHANGE_ASSIGNMENT[0], "change_assignment", "a Assign", show=True),
        Binding(kb.OPEN_IN_BROWSER[0], "open_in_browser", "o Open", show=True),
        Binding(kb.REFRESH[0], "refresh", "r Refresh", show=True),
        Binding(kb.QUIT[0], "quit", "Quit", show=True),
        Binding(kb.SHOW_HELP[0], "show_help", "Help", show=False),
    ]

    DEFAULT_CSS = """
    #search-bar {
        dock: bottom;
        height: 1;
        display: none;
    }
    #search-bar.visible {
        display: block;
    }
    """

    def __init__(
        self,
        client: MondayClient,
        board_id: str,
        user_lookup: dict[str, str] | None = None,
        current_user_id: str = "",
        account_slug: str = "",
    ) -> None:
        super().__init__()
        self.client = client
        self.board_id = board_id
        self.user_lookup = user_lookup or {}
        self.current_user_id = current_user_id
        self.current_user_name = (
            user_lookup.get(current_user_id, "") if current_user_id else ""
        )
        self.account_slug = account_slug
        self.board: Board | None = None
        self.current_group_idx: int = 0
        self.items: list[BoardItem] = []
        self._visible_columns: list[str] = []
        self._column_types: dict[str, str] = {}
        # Search state
        self._search_query: str = ""
        self._match_indices: list[int] = []  # row indices that match
        self._current_match: int = -1  # index into _match_indices

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="group-header")
        yield DataTable(id="board-table")
        yield Input(placeholder="/search...", id="search-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#board-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self.load_board()

    # --- Search ---

    def action_start_search(self) -> None:
        search_bar = self.query_one("#search-bar", Input)
        search_bar.add_class("visible")
        search_bar.value = ""
        search_bar.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-bar":
            self._search_query = event.value.strip().lower()
            self._update_matches()
            self._populate_table()
            if self._match_indices:
                self._current_match = 0
                self._jump_to_match()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar":
            self._close_search_bar()

    def _close_search_bar(self) -> None:
        search_bar = self.query_one("#search-bar", Input)
        search_bar.remove_class("visible")
        table = self.query_one("#board-table", DataTable)
        table.focus()

    def _update_matches(self) -> None:
        self._match_indices = []
        self._current_match = -1
        if not self._search_query:
            return
        query = self._search_query
        for i, item in enumerate(self.items):
            # Search across item name and all column values
            searchable = item.name.lower()
            for v in item.column_values.values():
                searchable += " " + v.lower()
            if query in searchable:
                self._match_indices.append(i)

    def _jump_to_match(self) -> None:
        if not self._match_indices or self._current_match < 0:
            return
        row_idx = self._match_indices[self._current_match]
        table = self.query_one("#board-table", DataTable)
        table.move_cursor(row=row_idx)
        self._update_search_status()

    def _update_search_status(self) -> None:
        header = self.query_one("#group-header", Static)
        if not self.board or not self.board.groups:
            return
        group = self.board.groups[self.current_group_idx]
        base = (
            f" [{group.color}]\u25cf[/] {group.title}  "
            f"({self.current_group_idx + 1}/{len(self.board.groups)})"
        )
        if self._search_query and self._match_indices:
            base += f"  /{self._search_query} [{self._current_match + 1}/{
                len(self._match_indices)
            }]"
        elif self._search_query:
            base += f"  /{self._search_query} [no matches]"
        header.update(base)

    def action_next_match(self) -> None:
        if not self._match_indices:
            return
        self._current_match = (self._current_match + 1) % len(self._match_indices)
        self._jump_to_match()

    def action_prev_match(self) -> None:
        if not self._match_indices:
            return
        self._current_match = (self._current_match - 1) % len(self._match_indices)
        self._jump_to_match()

    # --- Data loading ---

    @work
    async def load_board(self) -> None:
        cached = cache.get("board_detail", self.board_id, ttl=cache.TTL_BOARD_DETAIL)
        if cached:
            api_board = ApiBoard.from_dict(cached)
        else:
            data = await self.client.execute(
                queries.BOARD_DETAIL, {"board_id": int(self.board_id)}
            )
            boards = data.get("boards", [])
            if not boards:
                self.query_one("#group-header", Static).update("Board not found")
                return
            cached = boards[0]
            cache.set("board_detail", self.board_id, cached, ttl=cache.TTL_BOARD_DETAIL)
            api_board = ApiBoard.from_dict(cached)

        self.board = map_board(api_board)
        self._compute_visible_columns()
        self.current_group_idx = 0
        self._setup_table_columns()
        await self._load_group_items()

    def _compute_visible_columns(self) -> None:
        if not self.board:
            return
        self._visible_columns = []
        self._column_types = {}
        for col in self.board.columns:
            if col.type in SKIP_TYPES:
                continue
            self._visible_columns.append(col.title)
            self._column_types[col.title] = col.type

    def _setup_table_columns(self) -> None:
        table = self.query_one("#board-table", DataTable)
        table.clear(columns=True)
        table.add_column("Item", key="name")
        for title in self._visible_columns:
            table.add_column(title, key=title)

    async def _load_group_items(self) -> None:
        if not self.board or not self.board.groups:
            return

        group = self.board.groups[self.current_group_idx]
        header = self.query_one("#group-header", Static)
        header.update(
            f" [{group.color}]\u25cf[/] {group.title}  "
            f"({self.current_group_idx + 1}/{len(self.board.groups)})"
        )

        cache_key = f"{self.board_id}:{group.id}"
        cached = cache.get("group_items", cache_key, ttl=cache.TTL_GROUP_ITEMS)

        if cached:
            raw_items = cached
        else:
            data = await self.client.execute(
                queries.GROUP_ITEMS,
                {"board_id": int(self.board_id), "group_id": group.id, "limit": 100},
            )
            boards = data.get("boards", [])
            groups = boards[0].get("groups", []) if boards else []
            items_page = groups[0].get("items_page", {}) if groups else {}
            raw_items = items_page.get("items", [])

            cursor = items_page.get("cursor")
            while cursor:
                page_data = await self.client.execute(
                    queries.NEXT_ITEMS_PAGE, {"cursor": cursor, "limit": 100}
                )
                next_page = page_data.get("next_items_page", {})
                raw_items.extend(next_page.get("items", []))
                cursor = next_page.get("cursor")

            cache.set("group_items", cache_key, raw_items, ttl=cache.TTL_GROUP_ITEMS)

        api_items = [ApiItem.from_dict(item) for item in raw_items]
        self.items = [map_board_item(ai, self.user_lookup) for ai in api_items]
        # Reset search on group change
        self._search_query = ""
        self._match_indices = []
        self._current_match = -1
        self._populate_table()

    # --- Rendering ---

    def _populate_table(self) -> None:
        table = self.query_one("#board-table", DataTable)
        # Remember selected item to restore after refresh
        selected_id = None
        if table.row_count > 0:
            try:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                selected_id = str(row_key.value)
            except Exception:
                pass
        table.clear()
        restore_row = 0
        for i, item in enumerate(self.items):
            if item.id == selected_id:
                restore_row = i
            is_match = i in self._match_indices if self._search_query else False
            name_cell = self._style_name(item.name, is_match)
            row: list[str | Text] = [name_cell]
            for col_title in self._visible_columns:
                raw = item.column_values.get(col_title, "")
                col_type = self._column_types.get(col_title, "")
                row.append(self._style_cell(raw, col_type))
            table.add_row(*row, key=item.id)
        if self.items:
            table.move_cursor(row=restore_row)

    def _style_name(self, name: str, is_match: bool) -> str | Text:
        if is_match and self._search_query:
            # Highlight the matching substring
            text = Text(name)
            lower = name.lower()
            start = lower.find(self._search_query)
            if start >= 0:
                text.stylize(
                    MATCH_HIGHLIGHT_STYLE, start, start + len(self._search_query)
                )
            return text
        return name

    def _style_cell(self, value: str, col_type: str) -> str | Text:
        if not value:
            return ""
        if col_type in STATUS_TYPES:
            key = value.lower().strip()
            if key in STATUS_DISPLAY:
                short, fg, bg = STATUS_DISPLAY[key]
                return Text(f" {short} ", style=f"bold {fg} on {bg}")
            return Text(f" {value} ", style="bold grey23 on grey70")
        if col_type in PEOPLE_TYPES:
            names = [n.strip() for n in value.split(",")]
            parts = Text()
            for i, name in enumerate(names):
                if i > 0:
                    parts.append(", ")
                is_me = self.current_user_name and name == self.current_user_name
                short = _shorten_name(name)
                if is_me:
                    parts.append(short, style=MY_USER_STYLE)
                else:
                    parts.append(short)
            return parts
        return value

    # --- Selection ---

    def _get_selected_item(self) -> BoardItem | None:
        table = self.query_one("#board-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        row_id = str(row_key.value)
        for item in self.items:
            if item.id == row_id:
                return item
        return None

    # --- Actions ---

    def action_prev_group(self) -> None:
        if not self.board or not self.board.groups:
            return
        self.current_group_idx = (self.current_group_idx - 1) % len(self.board.groups)
        self._setup_table_columns()
        self._switch_group()

    def action_next_group(self) -> None:
        if not self.board or not self.board.groups:
            return
        self.current_group_idx = (self.current_group_idx + 1) % len(self.board.groups)
        self._setup_table_columns()
        self._switch_group()

    @work
    async def _switch_group(self) -> None:
        await self._load_group_items()

    def action_switch_board(self) -> None:
        self.app.action_command_palette()

    def action_edit_title(self) -> None:
        item = self._get_selected_item()
        if not item:
            return
        from mui.screens.item import EditTitleModal

        self.app.push_screen(
            EditTitleModal(item.name),
            callback=lambda new_title: (
                self._apply_title(item, new_title) if new_title else None
            ),
        )

    @work
    async def _apply_title(self, item: BoardItem, new_title: str) -> None:
        await self.client.execute(
            queries.CHANGE_ITEM_NAME,
            {
                "board_id": int(self.board_id),
                "item_id": int(item.id),
                "column_id": "name",
                "value": new_title,
            },
        )
        cache.invalidate(
            "group_items",
            f"{self.board_id}:{self.board.groups[self.current_group_idx].id}",
        )
        await self._load_group_items()

    def action_change_status(self) -> None:
        item = self._get_selected_item()
        if not item or not self.board:
            return
        status_cols = [c for c in self.board.columns if c.type in STATUS_TYPES]
        if not status_cols:
            return
        col = status_cols[0]
        labels = self._parse_status_labels(col.settings)
        from mui.screens.item import StatusPickerModal

        self.app.push_screen(
            StatusPickerModal(labels),
            callback=lambda label: (
                self._apply_status(item, col.id, label) if label else None
            ),
        )

    def _parse_status_labels(self, settings: str | dict) -> list[str]:
        if not settings:
            return []
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except json.JSONDecodeError:
                return []
        labels = settings.get("labels", [])
        # Labels can be a list of dicts or a dict of index→label
        if isinstance(labels, list):
            return [item["label"] for item in labels if item.get("label")]
        if isinstance(labels, dict):
            return [v for v in labels.values() if v]
        return []

    @work
    async def _apply_status(self, item: BoardItem, column_id: str, label: str) -> None:
        await self.client.execute(
            queries.CHANGE_STATUS,
            {
                "board_id": int(self.board_id),
                "item_id": int(item.id),
                "column_id": column_id,
                "value": label,
            },
        )
        cache.invalidate(
            "group_items",
            f"{self.board_id}:{self.board.groups[self.current_group_idx].id}",
        )
        await self._load_group_items()

    def action_change_assignment(self) -> None:
        item = self._get_selected_item()
        if not item or not self.board:
            return
        people_cols = [c for c in self.board.columns if c.type in PEOPLE_TYPES]
        if not people_cols:
            return
        col = people_cols[0]
        users = [(uid, name) for uid, name in self.user_lookup.items()]
        from mui.screens.item import PersonPickerModal

        self.app.push_screen(
            PersonPickerModal(users),
            callback=lambda user_id: (
                self._apply_person(item, col.id, user_id) if user_id else None
            ),
        )

    @work
    async def _apply_person(
        self, item: BoardItem, column_id: str, user_id: str
    ) -> None:
        value = json.dumps(
            {"personsAndTeams": [{"id": int(user_id), "kind": "person"}]}
        )
        await self.client.execute(
            queries.CHANGE_COLUMN_VALUE,
            {
                "board_id": int(self.board_id),
                "item_id": int(item.id),
                "column_id": column_id,
                "value": value,
            },
        )
        cache.invalidate(
            "group_items",
            f"{self.board_id}:{self.board.groups[self.current_group_idx].id}",
        )
        await self._load_group_items()

    def action_open_in_browser(self) -> None:
        item = self._get_selected_item()
        if not item:
            return
        slug = self.account_slug or "view"
        url = f"https://{slug}.monday.com/boards/{self.board_id}/pulses/{item.id}"
        webbrowser.open(url)

    def action_refresh(self) -> None:
        if self.board:
            cache.invalidate("board_detail", self.board_id)
            for group in self.board.groups:
                cache.invalidate("group_items", f"{self.board_id}:{group.id}")
        self.load_board()

    def action_show_help(self) -> None:
        from mui.screens.item import HelpModal

        self.app.push_screen(HelpModal())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        item_id = str(event.row_key.value)
        from mui.screens.item import ItemDetailModal

        self.app.push_screen(ItemDetailModal(self.client, item_id, self.user_lookup))
