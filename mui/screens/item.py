"""Item detail modal, status picker, person picker, and help modal."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from mui.api.client import MondayClient
from mui.api.models import ApiItem
from mui.api import queries
from mui import cache, keybindings as kb
from mui.mappers import map_item_detail
from mui.models import ItemDetail, Update


class ItemDetailModal(ModalScreen):
    """Shows full item info, column values, and interactive updates."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding(kb.NEXT_COMMENT[0], "next_comment", "Next comment", show=False),
        Binding(kb.PREV_COMMENT[0], "prev_comment", "Prev comment", show=False),
        Binding(kb.REPLY_TO_COMMENT[0], "reply_comment", "Reply", show=False),
        Binding(kb.NEW_COMMENT[0], "new_comment", "New comment", show=False),
        Binding(kb.TOGGLE_LIKE[0], "toggle_like", "Like", show=False),
    ]

    DEFAULT_CSS = """
    ItemDetailModal {
        align: center middle;
    }
    #item-detail-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
        overflow: auto auto;
    }
    #item-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .section-header {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }
    #updates-list {
        height: auto;
    }
    #updates-list > ListItem {
        height: auto;
        padding: 0;
    }
    .update-item {
        padding: 0 1;
        height: auto;
    }
    .update-item-selected {
        padding: 0 1;
        height: auto;
        background: $accent 20%;
    }
    .update-meta {
        color: $text-muted;
    }
    .update-body {
        margin-top: 0;
    }
    .reply-entry {
        margin-left: 2;
        color: $text-muted;
    }
    #hint-bar {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        client: MondayClient,
        item_id: str,
        user_lookup: dict[str, str] | None = None,
        current_user_id: str = "",
    ) -> None:
        super().__init__()
        self.client = client
        self.item_id = item_id
        self.user_lookup = user_lookup or {}
        self.current_user_id = current_user_id
        self._updates: list[Update] = []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="item-detail-container"):
            yield Static("Loading...", id="item-title")
            yield Static("", id="item-fields")
            yield Static("Updates", classes="section-header", id="updates-header")
            yield ListView(id="updates-list")
        yield Static("j/k navigate  r reply  c comment  l like  Esc close", id="hint-bar")

    def on_mount(self) -> None:
        self.load_item()

    @work
    async def load_item(self) -> None:
        cached = cache.get("item_detail", self.item_id, ttl=cache.TTL_ITEM_DETAIL)
        if cached:
            raw = cached
        else:
            data = await self.client.execute(queries.ITEM_DETAIL, {"item_id": int(self.item_id)})
            items = data.get("items", [])
            if not items:
                self.query_one("#item-title", Static).update("Item not found")
                return
            raw = items[0]
            cache.set("item_detail", self.item_id, raw, ttl=cache.TTL_ITEM_DETAIL)

        api_item = ApiItem.from_dict(raw)
        detail = map_item_detail(api_item, self.user_lookup)
        self._updates = detail.updates

        self.query_one("#item-title", Static).update(detail.name)

        fields_text = ""
        if detail.group_title:
            fields_text += f"Group: {detail.group_title}\n"
        if detail.board_name:
            fields_text += f"Board: {detail.board_name}\n"
        for col_title, value in detail.column_values.items():
            fields_text += f"{col_title}: {value}\n"
        self.query_one("#item-fields", Static).update(fields_text.rstrip())

        await self._render_updates()

    async def _render_updates(self) -> None:
        list_view = self.query_one("#updates-list", ListView)
        await list_view.clear()

        if not self._updates:
            await list_view.mount(ListItem(Static("No updates yet.")))
            return

        for i, update in enumerate(self._updates):
            liked = update.is_liked_by(self.current_user_id)
            heart = "\u2665" if liked else "\u2661"
            likes_str = f"  {heart} {update.like_count}" if update.like_count else f"  {heart}"
            meta = f"{update.author} \u00b7 {update.created_at}{likes_str}"

            children: list[Static] = [
                Static(meta, classes="update-meta"),
                Static(update.text, classes="update-body"),
            ]
            for reply in update.replies:
                r_liked = reply.is_liked_by(self.current_user_id)
                r_heart = "\u2665" if r_liked else "\u2661"
                r_likes = f" {r_heart}{reply.like_count}" if reply.like_count else ""
                reply_text = f"\u21b3 {reply.author}: {reply.text}{r_likes}"
                children.append(Static(reply_text, classes="reply-entry"))

            css_class = "update-item-selected" if i == self._selected_index else "update-item"
            await list_view.mount(ListItem(Vertical(*children, classes=css_class)))

        # Clamp index and highlight
        if self._selected_index >= len(self._updates):
            self._selected_index = max(0, len(self._updates) - 1)
        list_view.index = self._selected_index

    def _refresh_highlight(self) -> None:
        """Update CSS classes to reflect current selection."""
        list_view = self.query_one("#updates-list", ListView)
        for i, li in enumerate(list_view.query(ListItem)):
            container = li.query_one(Vertical)
            if container is None:
                continue
            if i == self._selected_index:
                container.remove_class("update-item")
                container.add_class("update-item-selected")
            else:
                container.remove_class("update-item-selected")
                container.add_class("update-item")

    def action_next_comment(self) -> None:
        if not self._updates:
            return
        self._selected_index = min(self._selected_index + 1, len(self._updates) - 1)
        self.query_one("#updates-list", ListView).index = self._selected_index
        self._refresh_highlight()

    def action_prev_comment(self) -> None:
        if not self._updates:
            return
        self._selected_index = max(self._selected_index - 1, 0)
        self.query_one("#updates-list", ListView).index = self._selected_index
        self._refresh_highlight()

    def action_reply_comment(self) -> None:
        if not self._updates:
            return
        update = self._updates[self._selected_index]
        self.app.push_screen(
            CommentEditorModal(f"Reply to {update.author}"),
            callback=lambda text: self._post_reply(update.id, text) if text else None,
        )

    def action_new_comment(self) -> None:
        self.app.push_screen(
            CommentEditorModal("New comment"),
            callback=lambda text: self._post_comment(text) if text else None,
        )

    def action_toggle_like(self) -> None:
        if not self._updates:
            return
        update = self._updates[self._selected_index]
        if update.is_liked_by(self.current_user_id):
            self._unlike(update.id)
        else:
            self._like(update.id)

    @work
    async def _post_comment(self, body: str) -> None:
        await self.client.execute(
            queries.CREATE_UPDATE,
            {"item_id": int(self.item_id), "body": body},
        )
        await self._reload()

    @work
    async def _post_reply(self, update_id: str, body: str) -> None:
        await self.client.execute(
            queries.CREATE_REPLY,
            {"parent_id": int(update_id), "body": body},
        )
        await self._reload()

    @work
    async def _like(self, update_id: str) -> None:
        await self.client.execute(
            queries.LIKE_UPDATE,
            {"update_id": int(update_id)},
        )
        await self._reload()

    @work
    async def _unlike(self, update_id: str) -> None:
        await self.client.execute(
            queries.UNLIKE_UPDATE,
            {"update_id": int(update_id)},
        )
        await self._reload()

    async def _reload(self) -> None:
        cache.invalidate("item_detail", self.item_id)
        saved_index = self._selected_index
        data = await self.client.execute(queries.ITEM_DETAIL, {"item_id": int(self.item_id)})
        items = data.get("items", [])
        if not items:
            return
        raw = items[0]
        cache.set("item_detail", self.item_id, raw, ttl=cache.TTL_ITEM_DETAIL)
        api_item = ApiItem.from_dict(raw)
        detail = map_item_detail(api_item, self.user_lookup)
        self._updates = detail.updates
        self._selected_index = saved_index
        await self._render_updates()

    def action_dismiss(self) -> None:
        self.dismiss(None)


class CommentEditorModal(ModalScreen[str | None]):
    """Multi-line text editor for posting comments/replies."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Submit", priority=True),
    ]

    DEFAULT_CSS = """
    CommentEditorModal {
        align: center middle;
    }
    #comment-editor-container {
        width: 70%;
        height: 50%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
    }
    #comment-editor-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #comment-textarea {
        height: 1fr;
    }
    #comment-hint {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, title: str = "Comment") -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="comment-editor-container"):
            yield Static(self._title, id="comment-editor-title")
            yield TextArea(id="comment-textarea")
            yield Static("Ctrl+S to submit, Esc to cancel", id="comment-hint")

    def on_mount(self) -> None:
        self.query_one("#comment-textarea", TextArea).focus()

    def action_submit(self) -> None:
        text = self.query_one("#comment-textarea", TextArea).text.strip()
        if text:
            self.dismiss(text)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class StatusPickerModal(ModalScreen[str | None]):
    """Pick a status label from a list."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    StatusPickerModal {
        align: center middle;
    }
    #picker-container {
        width: 40;
        max-height: 60%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
    }
    #picker-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, labels: list[str]) -> None:
        super().__init__()
        self.labels = labels

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-container"):
            yield Static("Select Status", id="picker-title")
            yield OptionList(*[Option(label, id=label) for label in self.labels], id="status-options")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditTitleModal(ModalScreen[str | None]):
    """Edit an item's title."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    EditTitleModal {
        align: center middle;
    }
    #edit-container {
        width: 60;
        height: auto;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
    }
    #edit-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, current_title: str) -> None:
        super().__init__()
        self.current_title = current_title

    def compose(self) -> ComposeResult:
        with Vertical(id="edit-container"):
            yield Static("Edit Title", id="edit-title")
            yield Input(value=self.current_title, id="title-input")

    def on_mount(self) -> None:
        inp = self.query_one("#title-input", Input)
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value and value != self.current_title:
            self.dismiss(value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PersonPickerModal(ModalScreen[str | None]):
    """Pick a person from the user list."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    PersonPickerModal {
        align: center middle;
    }
    #picker-container {
        width: 40;
        max-height: 60%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
    }
    #picker-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, users: list[tuple[str, str]]) -> None:
        super().__init__()
        self.users = users  # [(id, name), ...]

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-container"):
            yield Static("Assign Person", id="picker-title")
            yield OptionList(
                *[Option(name, id=uid) for uid, name in self.users],
                id="person-options",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GroupPickerModal(ModalScreen[str | None]):
    """Pick a target group/section to move items to."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    GroupPickerModal {
        align: center middle;
    }
    #picker-container {
        width: 50;
        max-height: 60%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
    }
    #picker-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, groups: list[tuple[str, str]], current_group_id: str) -> None:
        super().__init__()
        # [(id, title), ...] excluding the current group
        self.groups = [(gid, title) for gid, title in groups if gid != current_group_id]

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-container"):
            yield Static("Move to Section", id="picker-title")
            yield OptionList(
                *[Option(title, id=gid) for gid, title in self.groups],
                id="group-options",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpModal(ModalScreen):
    """Shows keybinding reference."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-container {
        width: 50;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: heavy $accent;
        padding: 1 2;
        overflow: auto auto;
    }
    #help-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    HELP_TEXT = """\
[bold]Board View[/]
j / k / ↑ / ↓   Navigate items
Ctrl+d / Ctrl+u  Half-page down / up
g / G            Jump to top / bottom
Enter            Open item detail / drop selected items
Esc              Close modal / go back
/                Search items (inline)
n / N            Next / previous match
Ctrl+p           Switch board
[ / ]            Previous / next group
i                Edit item title
s                Change status
d                Change deploy status
a                Change assignment (Tab toggle, Enter confirm)
Tab              Select / deselect item
m                Move selected to section
p                Set points
o                Open in browser
G                Open PR on GitHub
y                Copy URL to clipboard
r                Refresh (clear cache)
q                Quit
?                Show this help

[bold]Item Detail[/]
j / k            Navigate comments
r                Reply to selected comment
c                New top-level comment
l                Like / unlike comment
Esc              Close"""

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static("Keybindings", id="help-title")
            yield Static(self.HELP_TEXT)

    def action_dismiss(self) -> None:
        self.dismiss(None)
