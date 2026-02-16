"""First-run auth screen — prompts for API token."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Static


class AuthScreen(Screen[str]):
    """Prompts the user for their Monday.com API token."""

    DEFAULT_CSS = """
    AuthScreen {
        align: center middle;
    }
    #auth-container {
        width: 70;
        height: auto;
        padding: 2 4;
        border: heavy $accent;
        background: $surface;
    }
    #auth-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #auth-help {
        color: $text-muted;
        margin-bottom: 1;
    }
    #token-input {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-container"):
            yield Static("Monday.com TUI", id="auth-title")
            yield Label(
                "Enter your Monday.com API token.\n"
                "Find it at: Profile Picture → Developers → API token",
                id="auth-help",
            )
            yield Input(placeholder="Paste your API token here...", password=True, id="token-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        token = event.value.strip()
        if token:
            self.dismiss(token)
