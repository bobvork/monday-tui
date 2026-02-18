"""All keyboard mappings in one place."""

from __future__ import annotations

# Navigation
MOVE_UP = ("k", "up")
MOVE_DOWN = ("j", "down")
HALF_PAGE_UP = ("ctrl+u",)
HALF_PAGE_DOWN = ("ctrl+d",)
JUMP_TOP = ("g",)
JUMP_BOTTOM = ("shift+g",)

# Groups
PREV_GROUP = ("left_square_bracket",)
NEXT_GROUP = ("right_square_bracket",)

# Search
SEARCH_ITEMS = ("slash",)
NEXT_MATCH = ("n",)
PREV_MATCH = ("shift+n",)
SWITCH_BOARD = ("ctrl+p",)

# Actions
OPEN_ITEM = ("enter",)
CLOSE = ("escape",)
EDIT_TITLE = ("i",)
CHANGE_STATUS = ("s",)
CHANGE_DEPLOY_STATUS = ("d",)
CHANGE_ASSIGNMENT = ("a",)
REFRESH = ("r",)
QUIT = ("q",)
OPEN_IN_BROWSER = ("o",)
OPEN_PR = ("G",)
COPY_URL = ("y",)
TOGGLE_SELECT = ("tab",)
MOVE_TO_GROUP = ("m",)
SET_POINTS = ("p",)
SHOW_HELP = ("question_mark",)

# Item detail — comments
NEXT_COMMENT = ("j", "down")
PREV_COMMENT = ("k", "up")
REPLY_TO_COMMENT = ("r",)
NEW_COMMENT = ("c",)
TOGGLE_LIKE = ("l",)
