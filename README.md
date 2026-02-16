# mui - Monday.com Terminal UI

A terminal user interface for Monday.com. Navigate boards, view items, change statuses, and more — all from your terminal with vim-style keybindings.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd mui
uv sync
```

## Setup

Run `uv run mui` and you'll be prompted for your Monday.com API token on first launch.

To get your token: go to Monday.com > Profile Picture > Developers > API token > Show.

The token is stored in `~/.config/mui/config.toml`.

## Usage

```bash
uv run mui
```

On startup, mui opens the last board you viewed. If no board is saved, press `Ctrl+p` to search.

### Keybindings

| Key | Action |
|-----|--------|
| `j` / `k` / `↑` / `↓` | Navigate items |
| `Ctrl+d` / `Ctrl+u` | Half-page down / up |
| `g` / `G` | Jump to top / bottom |
| `[` / `]` | Previous / next group |
| `Enter` | Open item detail (updates, reactions) |
| `Esc` | Close modal / go back |
| `/` | Search items (inline, highlights matches) |
| `n` / `N` | Next / previous search match |
| `Ctrl+p` | Switch board (fuzzy search) |
| `i` | Edit item title |
| `s` | Change status (picker) |
| `a` | Change assignment (picker) |
| `o` | Open item in browser |
| `r` | Refresh (clears cache) |
| `q` | Quit |
| `?` | Show help |

All keybindings are defined in `mui/keybindings.py` for easy customization.

## Project Structure

```
mui/
├── app.py              Main Textual app, startup, board search command palette
├── config.py           Config loading/saving (~/.config/mui/config.toml)
├── models.py           Domain models (Board, BoardItem, ItemDetail, Update, User)
├── mappers.py          API response → domain model transforms
├── cache.py            Disk-based JSON cache (~/.cache/mui/)
├── keybindings.py      All key mappings in one place
├── api/
│   ├── client.py       Async Monday.com GraphQL client (httpx)
│   ├── models.py       API response dataclasses (raw shape)
│   └── queries.py      GraphQL query/mutation strings
├── screens/
│   ├── auth.py         First-run token entry
│   ├── board.py        Board view (main screen, groups, DataTable)
│   └── item.py         Item detail modal, status/person/title pickers, help
└── styles/
    └── app.tcss        Textual CSS styles
```

### Architecture

The data flows through two layers to decouple Monday.com's API shape from the TUI:

```
Monday.com GraphQL API → API models (api/models.py) → Domain models (models.py)
                          raw response shape            what screens/widgets use
                              ↑                              ↑
                          from_dict()                    mappers.py
```

API responses are cached as JSON files in `~/.cache/mui/` with per-query TTLs to conserve rate limits (Monday.com allows as few as 200 calls/day on free plans).
