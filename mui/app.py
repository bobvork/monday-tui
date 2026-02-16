"""Main Textual app for Monday.com TUI."""

from __future__ import annotations

from functools import partial
from typing import Any

from textual import work
import traceback as tb_module

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widgets import Footer, Static

from mui import cache
from mui.api.client import MondayClient
from mui.api.models import ApiUser
from mui.api import queries
from mui.config import Config
from mui.mappers import map_user


class BoardSearchProvider(Provider):
    """Command palette provider for fuzzy board search."""

    async def startup(self) -> None:
        app: MuiApp = self.app  # type: ignore[assignment]
        self.boards = await app.fetch_boards()

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for board in self.boards:
            score = matcher.match(board["name"])
            if score > 0:
                app: MuiApp = self.app  # type: ignore[assignment]
                yield Hit(
                    score,
                    matcher.highlight(board["name"]),
                    partial(app.open_board, board["id"]),
                    help=f"Open board {board['id']}",
                )


class MuiApp(App):
    """Monday.com TUI."""

    TITLE = "mui"
    CSS_PATH = "styles/app.tcss"
    COMMANDS = App.COMMANDS | {BoardSearchProvider}
    COMMAND_PALETTE_BINDING = "ctrl+p"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
    ]

    def _fatal_error(self) -> None:
        """Print a clean traceback without locals."""
        import sys
        self.bell()
        text = "".join(tb_module.format_exception(*sys.exc_info()))
        from rich.segment import Segments
        from rich.text import Text
        renderable = Segments(self.console.render(Text(text), self.console.options))
        self._exit_renderables.append(renderable)
        self._close_messages_no_wait()

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.load()
        self.client: MondayClient | None = None
        self.user_lookup: dict[str, str] = {}
        self.current_user_id: str = ""
        self.account_slug: str = ""
        self._boards_cache: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Static("Starting...", id="status")
        yield Footer()

    def on_mount(self) -> None:
        if not self.config.has_token:
            self._prompt_for_token()
        else:
            self._initialize_client()

    def _prompt_for_token(self) -> None:
        from mui.screens.auth import AuthScreen
        self.push_screen(AuthScreen(), callback=self._on_token_received)

    def _on_token_received(self, token: str | None) -> None:
        if not token:
            self.exit()
            return
        self.config.api_token = token
        self.config.save()
        self._initialize_client()

    def _initialize_client(self) -> None:
        self.client = MondayClient(self.config.api_token)
        self._startup()

    @work
    async def _startup(self) -> None:
        await self._load_me()
        await self._load_users()
        if self.config.last_board_id:
            self.open_board(self.config.last_board_id)
        else:
            self.query_one("#status", Static).update(
                "Press / to search for a board"
            )

    async def _load_me(self) -> None:
        if not self.client:
            return
        data = await self.client.execute(queries.ME)
        me = data.get("me", {})
        self.current_user_id = str(me.get("id", ""))
        account = me.get("account") or {}
        self.account_slug = account.get("slug", "")

    async def _load_users(self) -> None:
        if not self.client:
            return
        cached = cache.get("users", "", ttl=cache.TTL_USERS)
        if cached:
            raw_users = cached
        else:
            data = await self.client.execute(queries.USERS_LIST)
            raw_users = data.get("users", [])
            cache.set("users", "", raw_users, ttl=cache.TTL_USERS)
        for u in raw_users:
            api_user = ApiUser.from_dict(u)
            self.user_lookup[api_user.id] = api_user.name

    async def fetch_boards(self) -> list[dict[str, str]]:
        if self._boards_cache:
            return self._boards_cache

        if not self.client:
            return []

        cached = cache.get("boards_list", "", ttl=cache.TTL_BOARDS)
        if cached:
            self._boards_cache = cached
            return cached

        all_boards: list[dict[str, str]] = []
        page = 1
        while True:
            data = await self.client.execute(
                queries.BOARDS_LIST, {"limit": 100, "page": page}
            )
            boards = data.get("boards", [])
            if not boards:
                break
            for b in boards:
                all_boards.append({"id": str(b["id"]), "name": b["name"]})
            if len(boards) < 100:
                break
            page += 1

        cache.set("boards_list", "", all_boards, ttl=cache.TTL_BOARDS)
        self._boards_cache = all_boards
        return all_boards

    def open_board(self, board_id: str) -> None:
        self.config.last_board_id = board_id
        self.config.save()

        from mui.screens.board import BoardScreen

        # Pop existing board screen if we're switching boards
        if isinstance(self.screen, BoardScreen):
            self.pop_screen()

        screen = BoardScreen(self.client, board_id, self.user_lookup, self.current_user_id, self.account_slug)
        self.push_screen(screen)


def main() -> None:
    app = MuiApp()
    app.run()


if __name__ == "__main__":
    main()
