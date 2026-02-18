"""Item detail modal, status picker, person picker, and help modal."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, OptionList, Static
from textual.widgets.option_list import Option

from mui.api.client import MondayClient
from mui.api.models import ApiItem
from mui.api import queries
from mui import cache
from mui.mappers import map_item_detail
from mui.models import ItemDetail, Update


class ItemDetailModal(ModalScreen):
    """Shows full item info, column values, and updates with reactions."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
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
    .update-entry {
        margin-top: 1;
        padding: 0 1;
    }
    .update-meta {
        color: $text-muted;
    }
    .reply-entry {
        margin-left: 2;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        client: MondayClient,
        item_id: str,
        user_lookup: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.item_id = item_id
        self.user_lookup = user_lookup or {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="item-detail-container"):
            yield Static("Loading...", id="item-title")
            yield Static("", id="item-fields")
            yield Static("Updates", classes="section-header", id="updates-header")
            yield Vertical(id="updates-list")

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

        self.query_one("#item-title", Static).update(detail.name)

        fields_text = ""
        if detail.group_title:
            fields_text += f"Group: {detail.group_title}\n"
        if detail.board_name:
            fields_text += f"Board: {detail.board_name}\n"
        for col_title, value in detail.column_values.items():
            fields_text += f"{col_title}: {value}\n"
        self.query_one("#item-fields", Static).update(fields_text.rstrip())

        updates_container = self.query_one("#updates-list", Vertical)
        await updates_container.remove_children()

        if not detail.updates:
            await updates_container.mount(Static("No updates yet."))
        else:
            for update in detail.updates:
                likes_str = f"  [{update.like_count} like{'s' if update.like_count != 1 else ''}]" if update.like_count else ""
                meta = f"{update.author} · {update.created_at}{likes_str}"
                await updates_container.mount(Static(meta, classes="update-meta"))
                await updates_container.mount(Static(update.text, classes="update-entry"))
                for reply in update.replies:
                    reply_likes = f"  [{reply.like_count} like{'s' if reply.like_count != 1 else ''}]" if reply.like_count else ""
                    reply_text = f"↳ {reply.author}: {reply.text}{reply_likes}"
                    await updates_container.mount(Static(reply_text, classes="reply-entry"))

    def action_dismiss(self) -> None:
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
j / k / ↑ / ↓   Navigate items
Ctrl+d / Ctrl+u  Half-page down / up
g / G            Jump to top / bottom
Enter            Open item detail
Esc              Close modal / go back
/                Search items (inline)
n / N            Next / previous match
Ctrl+p           Switch board
[ / ]            Previous / next group
i                Edit item title
s                Change status
a                Change assignment (Tab toggle, Enter confirm)
Tab              Select / deselect item
m                Move selected to section
p                Set points
o                Open in browser
y                Copy URL to clipboard
r                Refresh (clear cache)
q                Quit
?                Show this help"""

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static("Keybindings", id="help-title")
            yield Static(self.HELP_TEXT)

    def action_dismiss(self) -> None:
        self.dismiss(None)
