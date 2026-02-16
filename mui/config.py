from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mui"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class Config:
    api_token: str = ""
    last_board_id: str = ""

    @staticmethod
    def load() -> Config:
        if not CONFIG_FILE.exists():
            return Config()
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        return Config(
            api_token=data.get("api_token", ""),
            last_board_id=str(data.get("last_board_id", "")),
        )

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = []
        lines.append(f'api_token = "{self.api_token}"')
        if self.last_board_id:
            lines.append(f'last_board_id = "{self.last_board_id}"')
        CONFIG_FILE.write_text("\n".join(lines) + "\n")

    @property
    def has_token(self) -> bool:
        return bool(self.api_token)
