# Monday.com TUI (`mui`) - Project Plan

## Overview

A terminal user interface for Monday.com built with Python, Textual, and the Monday.com GraphQL API. Board-focused: search for a board, view and interact with its items.

## Tech Stack (Decided)

| Component | Choice | Notes |
|-----------|--------|-------|
| Language | Python 3.11+ | `tomllib` in stdlib |
| Package manager | `uv` | `uv init` to bootstrap |
| TUI framework | [Textual](https://textual.textualize.io/) | 40+ widgets, CSS styling, async-native |
| HTTP client | `httpx` | Async-native, thin GraphQL wrapper on top |
| Config | `~/.config/mui/config.toml` | `tomllib` for reading, manual TOML write for setup |
| Monday.com API | GraphQL (`https://api.monday.com/v2`) | Auth via personal API token in `Authorization` header |

## Monday.com API Summary

- **Type**: GraphQL (queries + mutations)
- **Auth**: Personal V2 API token passed as `Authorization` header
- **Endpoint**: `https://api.monday.com/v2`
- **Key entities**: Workspaces, Boards, Groups, Items (rows), Column Values, Users, Updates (comments)
- **Rate limits** (vary by plan):
  - Daily calls: 200 (free) to 25,000 (enterprise)
  - Per-minute: 1,000–5,000 requests depending on plan
  - Complexity budget: 5M–10M points/minute
  - Concurrency: 40–250 simultaneous requests

---

## Decisions Made

| # | Topic | Decision |
|---|-------|----------|
| 1 | HTTP client | `httpx` — async, lightweight, thin GraphQL wrapper on top |
| 2 | Config/auth | `~/.config/mui/config.toml` — stable auth, no env var needed |
| 3 | Python version | 3.11+ — `tomllib` in stdlib, broad compatibility |
| 4 | MVP scope | Board-focused — see below |
| 5 | Data modeling | Dataclasses with a transform/mapper layer — see below |
| 6 | Caching | Disk-based JSON cache in `~/.cache/mui/` — survives restarts, essential for dev |
| 7 | Keybindings | Vim-style (`j/k`, `/` search, Enter to open, etc.) |

---

## MVP Scope

### In scope

- **First-run auth** — prompt for API token, write to `config.toml`
- **Board search** — find a board by name (command palette / search bar)
- **Board view (main screen)** — DataTable showing items grouped by group, with columns:
  - Item name
  - Status
  - Assigned people
  - Other visible columns (date, text, numbers, etc.)
- **Item detail** — open with Enter; shows full item info + updates (comments) + reactions
- **Inline editing** — keyboard shortcuts to change status, person assignment, and other column values directly from the board view
- **Reactions** — view reactions on item updates

### UX Decisions

- **Startup**: Open last-used board (stored in `config.toml`). If none, show board search.
- **Board search**: Command-palette-style overlay with fuzzy search (like VS Code `Ctrl+P`). Triggered by `/`.
- **Item detail**: Modal overlay on top of the board view (board stays visible underneath).
- **Inline editing**: Pressing `s` opens a picker listing the available statuses for that column. Same pattern for other column types.
- **Groups/sections**: Show one group at a time. Sticky group title pinned at the top of the board view (visible even when scrolled). `[` / `]` to navigate to previous / next group.

### Out of scope (later)

- Item creation
- Subitems
- Activity log
- Documents, dashboards
- Board creation/configuration
- Automations / integrations
- File uploads
- Notifications

---

## Data Architecture

Two-layer model to decouple the Monday.com API shape from TUI concerns:

```
Monday.com API (JSON) ──► API models (dataclasses) ──► Domain models (dataclasses)
                          raw API shape                 what the TUI works with
                          in api/models.py              in models.py
```

- **API models** — mirror the GraphQL response shape. Simple `@dataclass` classes with a `from_dict(data: dict)` classmethod to parse raw JSON. Keeps parsing in one place.
- **Domain models** — what screens and widgets consume. Flat, convenient, TUI-oriented. E.g. a `BoardItem` with `.status_label`, `.status_color`, `.assignees: list[str]` instead of nested column value structures.
- **Mappers** — functions in `mappers.py` that convert API models → domain models. Single place to update if the API response shape changes.

This avoids Pydantic's weight while keeping a clean separation. Dataclasses give us type hints and `__eq__`/`__repr__` for free.

---

## Project Structure

```
mui/
├── __init__.py
├── app.py              # Textual App, screen routing, keybindings
├── config.py           # Load/write ~/.config/mui/config.toml
├── models.py           # Domain models (what the TUI uses)
├── mappers.py          # API models → domain models
├── cache.py            # Disk-based JSON cache (~/.cache/mui/)
├── keybindings.py      # All key mappings in one place
├── api/
│   ├── __init__.py
│   ├── client.py       # Async Monday.com GraphQL client (httpx)
│   ├── queries.py      # GraphQL query/mutation strings
│   └── models.py       # API response dataclasses (raw shape)
├── screens/
│   ├── __init__.py
│   ├── board.py        # Board view (main screen)
│   ├── item.py         # Item detail screen/modal
│   └── auth.py         # First-run token setup
├── widgets/
│   ├── __init__.py
│   ├── board_table.py  # DataTable for board items
│   └── search.py       # Board search widget
└── styles/
    └── app.tcss        # Textual CSS styles
```

## Dependencies

```toml
[project]
name = "mui"
requires-python = ">=3.11"
dependencies = [
    "textual>=1.0",
    "httpx>=0.27",
]

[project.scripts]
mui = "mui.app:main"
```

---

## Caching

Disk-based JSON cache in `~/.cache/mui/`. Essential during development (survives TUI restarts) and protects against Monday.com's rate limits (as low as 200 calls/day on free plans).

- Cache files keyed by query hash (e.g. `~/.cache/mui/boards_<hash>.json`)
- Each file stores `{ "timestamp": ..., "ttl": ..., "data": ... }`
- TTL per query type: board list (5 min), board data (1 min), user list (10 min)
- Invalidate relevant cache entries on mutations (status change, assignment, etc.)
- `cache.py` module with simple `get` / `set` / `invalidate` functions

## Keybindings

Vim-style with arrow key support. Defined in a dedicated `keybindings.py` file so they're easy to change in one place.

| Key | Action |
|-----|--------|
| `j` / `k` / `↑` / `↓` | Move up / down in lists and tables |
| `Enter` | Open item detail |
| `Esc` | Back / close modal |
| `/` | Search for a board |
| `Ctrl+d` / `Ctrl+u` | Scroll half-screen down / up |
| `[` / `]` | Previous / next group (section) |
| `s` | Change status of selected item (opens picker) |
| `a` | Change assignment of selected item |
| `r` | Refresh current view (invalidate cache) |
| `q` | Quit |
| `g` / `G` | Jump to top / bottom |
| `?` | Show help / keybinding reference |

---

## Implementation Order

1. `uv init` + scaffold project structure + dependencies
2. Config loading + first-run auth screen
3. API client (httpx + GraphQL wrapper)
4. Board search screen
5. Board view with DataTable (items, groups, status, people)
6. Item detail modal (full info + updates + reactions)
7. Inline editing (status changes, assignments)
8. Keybindings + polish
