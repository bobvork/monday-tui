"""Board view screen — main working environment."""

from __future__ import annotations

import json
import re
import webbrowser
from typing import Any

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

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
# For color names: https://rich.readthedocs.io/en/latest/appendix/colors.html
# Status label → (short name, font color, background color)
STATUS_DISPLAY: dict[str, tuple[str, str, str]] = {
    "done": ("", "dark_green", "pale_green3"),
    "pull request": ("", "navy_blue", "light_sky_blue1"),
    "ready 4 test": ("󰤑", "navy_blue", "light_sky_blue1"),
    "work in progress": ("󰣪", "orange4", "khaki1"),
    "working on it": ("WiP", "orange4", "khaki1"),
    "blocked": ("", "dark_red", "indian_red1"),
    "backlog": ("-", "grey23", "grey70"),
    "stuck": ("Stuck", "dark_red", "indian_red1"),
    "meer info nodig": ("?", "dark_red", "indian_red1"),
    "genomineerd": ("", "blue_violet", "light_steel_blue"),
    "production": ("prod", "dark_green", "pale_green3"),
    "development": ("dev", "orange4", "khaki1"),
    "local": ("local", "grey23", "grey70"),
}

LINK_TYPES = {"link", "text"}
NUMBERS_TYPES = {"numbers"}
_GH_PR_RE = re.compile(r"https?://github\.com/[^/]+/([^/]+)/pull/(\d+)")
POINT_OPTIONS = ["1", "2", "3", "5", "8", "20", "40"]

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
        Binding(kb.CLOSE[0], "clear_selection", "Clear selection", show=False),
        Binding(kb.HALF_PAGE_UP[0], "half_page_up", "½ Page Up", show=False),
        Binding(kb.HALF_PAGE_DOWN[0], "half_page_down", "½ Page Down", show=False),
        Binding(kb.PREV_GROUP[0], "prev_group", "Prev", show=True),
        Binding(kb.NEXT_GROUP[0], "next_group", "Next", show=True),
        Binding(kb.SEARCH_ITEMS[0], "start_search", "Search", show=True, priority=True),
        Binding(kb.NEXT_MATCH[0], "next_match", "Next Match", show=False),
        Binding(kb.PREV_MATCH[0], "prev_match", "Prev Match", show=False),
        Binding(kb.SWITCH_BOARD[0], "switch_board", "^P Board", show=True),
        Binding(kb.EDIT_TITLE[0], "edit_title", "Edit", show=False),
        Binding(kb.CHANGE_STATUS[0], "change_status", "Status", show=False),
        Binding(kb.CHANGE_DEPLOY_STATUS[0], "change_deploy_status", "Deploy", show=False),
        Binding(kb.CHANGE_ASSIGNMENT[0], "change_assignment", "Assign", show=False),
        Binding(kb.OPEN_IN_BROWSER[0], "open_in_browser", "Open", show=True),
        Binding(kb.OPEN_PR[0], "open_pr", "Open PR", show=True, priority=True),
        Binding(kb.COPY_URL[0], "copy_url", "Copy URL", show=True),
        Binding(kb.TOGGLE_SELECT[0], "toggle_select", "Select", show=True, priority=True),
        Binding(kb.MOVE_TO_GROUP[0], "move_to_group", "Move", show=True),
        Binding(kb.SET_POINTS[0], "set_points", "Points", show=False),
        Binding(kb.REFRESH[0], "refresh", "Refresh", show=True),
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
    #points-picker, #status-picker, #person-picker {
        dock: bottom;
        height: auto;
        max-height: 12;
        display: none;
        background: $surface;
        border-top: solid $accent;
    }
    #points-picker.visible, #status-picker.visible, #person-picker.visible {
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
        # Multi-select state
        self._selected_ids: set[str] = set()
        # Inline picker state
        self._points_item: BoardItem | None = None
        self._points_column_id: str = ""
        self._status_items: list[BoardItem] = []
        self._status_column_id: str = ""
        self._person_item: BoardItem | None = None
        self._person_column_id: str = ""
        self._person_selected_ids: set[str] = set()  # toggled user IDs
        self._person_toggled: bool = False  # whether Tab was used
        self._person_options: list[tuple[str, str]] = []  # [(uid, name), ...]
        # Search state
        self._search_query: str = ""
        self._match_indices: list[int] = []  # row indices that match
        self._current_match: int = -1  # index into _match_indices

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="group-header")
        yield DataTable(id="board-table")
        yield OptionList(
            *[Option(p, id=p) for p in POINT_OPTIONS],
            id="points-picker",
        )
        yield OptionList(id="status-picker")
        yield OptionList(id="person-picker")
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
        table.add_column(Text.from_markup(f"Item [dim]\\[i][/dim]"), key="name")
        # Track status column index to assign s/d shortcuts
        status_idx = 0
        status_keys = ["s", "d"]
        for title in self._visible_columns:
            col_type = self._column_types.get(title, "")
            if col_type in STATUS_TYPES:
                hint = status_keys[status_idx] if status_idx < len(status_keys) else ""
                status_idx += 1
            elif col_type in PEOPLE_TYPES:
                hint = "a"
            elif col_type in NUMBERS_TYPES:
                hint = "p"
            else:
                hint = ""
            if hint:
                label = Text.from_markup(f"{title} [dim]\\[{hint}][/dim]")
            else:
                label = Text(title)
            table.add_column(label, key=title)

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
        # Reset selection and search on group change
        self._selected_ids.clear()
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
            is_selected = item.id in self._selected_ids
            name_cell = self._style_name(item.name, is_match, is_selected)
            row: list[str | Text] = [name_cell]
            for col_title in self._visible_columns:
                raw = item.column_values.get(col_title, "")
                col_type = self._column_types.get(col_title, "")
                row.append(self._style_cell(raw, col_type))
            table.add_row(*row, key=item.id)
        if self.items:
            table.move_cursor(row=restore_row)

    def _style_name(self, name: str, is_match: bool, is_selected: bool) -> str | Text:
        if len(name) > 90:
            name = name[:87] + "..."
        prefix = "● " if is_selected else "  "
        display = prefix + name
        if is_match and self._search_query:
            text = Text(display)
            # Offset by prefix length for highlight
            lower = name.lower()
            start = lower.find(self._search_query)
            if start >= 0:
                text.stylize(
                    MATCH_HIGHLIGHT_STYLE,
                    len(prefix) + start,
                    len(prefix) + start + len(self._search_query),
                )
            return text
        if is_selected:
            return Text(display, style="bold magenta")
        return display

    def _style_cell(self, value: str, col_type: str) -> str | Text:
        if not value:
            return ""
        if col_type in STATUS_TYPES:
            key = value.lower().strip()
            if key in STATUS_DISPLAY:
                short, fg, bg = STATUS_DISPLAY[key]
                return Text(f" {short} ", style=f"bold {fg} on {bg}")
            return Text(f" {value} ", style="bold grey23 on grey70")
        if col_type in LINK_TYPES:
            m = _GH_PR_RE.search(value)
            if m:
                return Text(f"{m.group(1)}#{m.group(2)}", style="cyan")
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

    def action_clear_selection(self) -> None:
        if self._selected_ids:
            self._selected_ids.clear()
            self._populate_table()

    def action_half_page_up(self) -> None:
        table = self.query_one("#board-table", DataTable)
        rows = table.size.height // 2 or 1
        for _ in range(rows):
            table.action_cursor_up()

    def action_half_page_down(self) -> None:
        table = self.query_one("#board-table", DataTable)
        rows = table.size.height // 2 or 1
        for _ in range(rows):
            table.action_cursor_down()

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

    def action_toggle_select(self) -> None:
        """Toggle selection on the current item and move cursor down."""
        item = self._get_selected_item()
        if not item:
            return
        if item.id in self._selected_ids:
            self._selected_ids.discard(item.id)
        else:
            self._selected_ids.add(item.id)
        self._populate_table()
        # Move cursor down after toggle
        table = self.query_one("#board-table", DataTable)
        table.action_cursor_down()

    def action_move_to_group(self) -> None:
        """Move selected items (or current item) to another group."""
        if not self.board or not self.board.groups:
            return
        # Use selected items, or fall back to current item
        item_ids = list(self._selected_ids) if self._selected_ids else []
        if not item_ids:
            item = self._get_selected_item()
            if item:
                item_ids = [item.id]
        if not item_ids:
            return

        current_group = self.board.groups[self.current_group_idx]
        groups = [(g.id, g.title) for g in self.board.groups]
        from mui.screens.item import GroupPickerModal

        self.app.push_screen(
            GroupPickerModal(groups, current_group.id),
            callback=lambda group_id: (
                self._apply_move_to_group(item_ids, group_id) if group_id else None
            ),
        )

    @work
    async def _apply_move_to_group(self, item_ids: list[str], group_id: str) -> None:
        for item_id in item_ids:
            await self.client.execute(
                queries.MOVE_ITEM_TO_GROUP,
                {"item_id": int(item_id), "group_id": group_id},
            )
        # Invalidate caches for source and target groups
        source_group = self.board.groups[self.current_group_idx]
        cache.invalidate("group_items", f"{self.board_id}:{source_group.id}")
        cache.invalidate("group_items", f"{self.board_id}:{group_id}")
        self._selected_ids.clear()
        await self._load_group_items()

    def action_set_points(self) -> None:
        """Open inline points picker for the current item."""
        item = self._get_selected_item()
        if not item or not self.board:
            return
        numbers_cols = [c for c in self.board.columns if c.type in NUMBERS_TYPES]
        if not numbers_cols:
            return
        self._points_item = item
        self._points_column_id = numbers_cols[0].id
        picker = self.query_one("#points-picker", OptionList)
        picker.add_class("visible")
        picker.highlighted = 0
        picker.focus()

    def _close_points_picker(self) -> None:
        picker = self.query_one("#points-picker", OptionList)
        picker.remove_class("visible")
        self._points_item = None
        self._points_column_id = ""
        self.query_one("#board-table", DataTable).focus()

    def _close_status_picker(self) -> None:
        picker = self.query_one("#status-picker", OptionList)
        picker.remove_class("visible")
        self._status_items = []
        self._status_column_id = ""
        self.query_one("#board-table", DataTable).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "points-picker" and self._points_item:
            value = str(event.option.prompt)
            item = self._points_item
            column_id = self._points_column_id
            self._close_points_picker()
            self._apply_points(item, column_id, value)
        elif event.option_list.id == "status-picker" and self._status_items:
            label = str(event.option.prompt)
            items = list(self._status_items)
            column_id = self._status_column_id
            self._close_status_picker()
            self._apply_status(items, column_id, label)
        elif event.option_list.id == "person-picker" and self._person_item:
            # If Tab wasn't used, assign the highlighted person directly
            if not self._person_toggled:
                user_ids = [str(event.option.id)]
            else:
                user_ids = list(self._person_selected_ids)
            item = self._person_item
            column_id = self._person_column_id
            self._close_person_picker()
            self._apply_persons(item, column_id, user_ids)

    def on_key(self, event) -> None:
        """Handle Escape and Tab in inline pickers."""
        # Person picker: Tab toggles selection
        person_picker = self.query_one("#person-picker", OptionList)
        if person_picker.has_class("visible"):
            if event.key == "tab" and self._person_item:
                highlighted = person_picker.highlighted
                if highlighted is not None and 0 <= highlighted < len(self._person_options):
                    uid = self._person_options[highlighted][0]
                    if uid in self._person_selected_ids:
                        self._person_selected_ids.discard(uid)
                    else:
                        self._person_selected_ids.add(uid)
                    self._person_toggled = True
                    self._refresh_person_picker()
                    person_picker.highlighted = highlighted
                event.stop()
                event.prevent_default()
                return
            if event.key == "escape":
                self._close_person_picker()
                event.stop()
                event.prevent_default()
                return

        for picker_id, close_fn in [
            ("#points-picker", self._close_points_picker),
            ("#status-picker", self._close_status_picker),
        ]:
            picker = self.query_one(picker_id, OptionList)
            if picker.has_class("visible") and event.key == "escape":
                close_fn()
                event.stop()
                event.prevent_default()
                return

    @work
    async def _apply_points(self, item: BoardItem, column_id: str, value: str) -> None:
        await self.client.execute(
            queries.CHANGE_STATUS,
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

    def _get_target_items(self) -> list[BoardItem]:
        """Return multi-selected items, or fall back to the cursor item."""
        if self._selected_ids:
            return [item for item in self.items if item.id in self._selected_ids]
        item = self._get_selected_item()
        return [item] if item else []

    def action_change_status(self) -> None:
        items = self._get_target_items()
        if not items or not self.board:
            return
        status_cols = [c for c in self.board.columns if c.type in STATUS_TYPES]
        if not status_cols:
            return
        col = status_cols[0]
        labels = self._parse_status_labels(col.settings)
        if not labels:
            return
        self._status_items = items
        self._status_column_id = col.id
        picker = self.query_one("#status-picker", OptionList)
        picker.clear_options()
        for label in labels:
            picker.add_option(Option(label, id=label))
        picker.add_class("visible")
        picker.highlighted = 0
        picker.focus()

    def _drop_selected(self) -> None:
        """Move selected items to below the current cursor position."""
        table = self.query_one("#board-table", DataTable)
        if table.row_count == 0:
            return
        # Find the cursor target
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        target_id = str(row_key.value)
        # Separate selected items from the rest, preserving order
        selected = [item for item in self.items if item.id in self._selected_ids]
        remaining = [item for item in self.items if item.id not in self._selected_ids]
        # Find insertion point in the remaining list
        insert_idx = 0
        for i, item in enumerate(remaining):
            if item.id == target_id:
                insert_idx = i + 1
                break
        # Insert selected items after target
        self.items = remaining[:insert_idx] + selected + remaining[insert_idx:]
        # Update cache so reorder persists across group switches
        self._update_group_cache()
        # Persist to API
        self._persist_positions(target_id, [item.id for item in selected])
        self._selected_ids.clear()
        # Re-render and place cursor on first dropped item
        self._populate_table()
        if selected:
            for i, item in enumerate(self.items):
                if item.id == selected[0].id:
                    table.move_cursor(row=i)
                    break

    @work
    async def _persist_positions(self, target_id: str, item_ids: list[str]) -> None:
        """Persist item positions to Monday.com API."""
        after_id = target_id
        for item_id in item_ids:
            await self.client.execute(
                queries.CHANGE_ITEM_POSITION,
                {
                    "item_id": int(item_id),
                    "relative_to": int(after_id),
                    "position_relative_method": "after_at",
                },
            )
            after_id = item_id

    def _update_group_cache(self) -> None:
        """Write current item order back into the group items cache."""
        if not self.board or not self.board.groups:
            return
        group = self.board.groups[self.current_group_idx]
        cache_key = f"{self.board_id}:{group.id}"
        cached = cache.get("group_items", cache_key, ttl=cache.TTL_GROUP_ITEMS)
        if not cached:
            return
        # Build a lookup from cached raw items by id
        raw_by_id = {str(raw["id"]): raw for raw in cached}
        reordered = [raw_by_id[item.id] for item in self.items if item.id in raw_by_id]
        cache.set("group_items", cache_key, reordered, ttl=cache.TTL_GROUP_ITEMS)

    def action_change_deploy_status(self) -> None:
        items = self._get_target_items()
        if not items or not self.board:
            return
        status_cols = [c for c in self.board.columns if c.type in STATUS_TYPES]
        if len(status_cols) < 2:
            return
        col = status_cols[1]
        labels = self._parse_status_labels(col.settings)
        if not labels:
            return
        self._status_items = items
        self._status_column_id = col.id
        picker = self.query_one("#status-picker", OptionList)
        picker.clear_options()
        for label in labels:
            picker.add_option(Option(label, id=label))
        picker.add_class("visible")
        picker.highlighted = 0
        picker.focus()

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
    async def _apply_status(self, items: list[BoardItem], column_id: str, label: str) -> None:
        for item in items:
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
        self._person_item = item
        self._person_column_id = col.id
        # Pre-select the item's current assignees
        self._person_selected_ids = set(item.assignee_ids)
        self._person_toggled = False
        # Count assignment frequency across all items in the current group
        freq: dict[str, int] = {}
        for it in self.items:
            for uid in it.assignee_ids:
                freq[uid] = freq.get(uid, 0) + 1
        # Sort users: most frequently assigned first, then alphabetical
        users = list(self.user_lookup.items())
        users.sort(key=lambda u: (-freq.get(u[0], 0), u[1].lower()))
        self._person_options = users
        self._refresh_person_picker()
        picker = self.query_one("#person-picker", OptionList)
        picker.add_class("visible")
        picker.highlighted = 0
        picker.focus()

    def _refresh_person_picker(self) -> None:
        """Rebuild person picker options showing selection state."""
        picker = self.query_one("#person-picker", OptionList)
        picker.clear_options()
        for uid, name in self._person_options:
            mark = "● " if uid in self._person_selected_ids else "  "
            picker.add_option(Option(f"{mark}{name}", id=uid))

    def _close_person_picker(self) -> None:
        picker = self.query_one("#person-picker", OptionList)
        picker.remove_class("visible")
        self._person_item = None
        self._person_column_id = ""
        self._person_selected_ids.clear()
        self._person_toggled = False
        self._person_options = []
        self.query_one("#board-table", DataTable).focus()

    @work
    async def _apply_persons(
        self, item: BoardItem, column_id: str, user_ids: list[str]
    ) -> None:
        value = json.dumps(
            {"personsAndTeams": [{"id": int(uid), "kind": "person"} for uid in user_ids]}
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

    def _item_url(self, item: BoardItem) -> str:
        slug = self.account_slug or "view"
        return f"https://{slug}.monday.com/boards/{self.board_id}/pulses/{item.id}"

    def _pr_url(self, item: BoardItem) -> str | None:
        for value in item.column_values.values():
            m = _GH_PR_RE.search(value)
            if m:
                return m.group(0)
        return None

    def action_open_pr(self) -> None:
        item = self._get_selected_item()
        if not item:
            return
        url = self._pr_url(item)
        if url:
            webbrowser.open(url)

    def action_open_in_browser(self) -> None:
        item = self._get_selected_item()
        if not item:
            return
        webbrowser.open(self._item_url(item))

    def action_copy_url(self) -> None:
        item = self._get_selected_item()
        if not item:
            return
        self.app.copy_to_clipboard(self._item_url(item))
        self.notify("URL copied to clipboard", timeout=2)

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
        if self._selected_ids:
            self._drop_selected()
            return
        item_id = str(event.row_key.value)
        from mui.screens.item import ItemDetailModal

        self.app.push_screen(
            ItemDetailModal(self.client, item_id, self.user_lookup, self.current_user_id)
        )
