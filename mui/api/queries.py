"""GraphQL query and mutation strings for the Monday.com API."""

ME = """
query {
  me {
    id
    name
    email
    account {
      slug
    }
  }
}
"""

BOARDS_LIST = """
query($limit: Int!, $page: Int!) {
  boards(limit: $limit, page: $page, state: active, order_by: used_at) {
    id
    name
  }
}
"""

BOARD_DETAIL = """
query($board_id: ID!) {
  boards(ids: [$board_id]) {
    id
    name
    columns {
      id
      title
      type
      settings
    }
    groups {
      id
      title
      color
      position
    }
  }
}
"""

GROUP_ITEMS = """
query($board_id: ID!, $group_id: String!, $limit: Int!) {
  boards(ids: [$board_id]) {
    groups(ids: [$group_id]) {
      items_page(limit: $limit) {
        cursor
        items {
          id
          name
          column_values {
            id
            type
            text
            value
            column {
              title
            }
            ... on StatusValue {
              label
            }
            ... on PeopleValue {
              persons_and_teams {
                id
                kind
              }
            }
          }
        }
      }
    }
  }
}
"""

NEXT_ITEMS_PAGE = """
query($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      column_values {
        id
        type
        text
        value
        column {
          title
        }
        ... on StatusValue {
          label
        }
        ... on PeopleValue {
          persons_and_teams {
            id
            kind
          }
        }
      }
    }
  }
}
"""

ITEM_DETAIL = """
query($item_id: ID!) {
  items(ids: [$item_id]) {
    id
    name
    created_at
    updated_at
    group {
      id
      title
    }
    board {
      id
      name
    }
    column_values {
      id
      type
      text
      value
      column {
        title
      }
      ... on StatusValue {
        label
      }
      ... on PeopleValue {
        persons_and_teams {
          id
          kind
        }
      }
    }
    updates(limit: 25) {
      id
      text_body
      created_at
      creator {
        id
        name
      }
      replies {
        id
        text_body
        created_at
        creator {
          id
          name
        }
      }
      likes {
        id
        creator_id
      }
    }
  }
}
"""

USERS_LIST = """
query {
  users(kind: non_guests, limit: 100) {
    id
    name
    email
  }
}
"""

CHANGE_STATUS = """
mutation($board_id: ID!, $item_id: ID!, $column_id: String!, $value: String!) {
  change_simple_column_value(
    board_id: $board_id
    item_id: $item_id
    column_id: $column_id
    value: $value
  ) {
    id
  }
}
"""

CHANGE_ITEM_NAME = """
mutation($board_id: ID!, $item_id: ID!, $column_id: String!, $value: String!) {
  change_simple_column_value(
    board_id: $board_id
    item_id: $item_id
    column_id: $column_id
    value: $value
  ) {
    id
    name
  }
}
"""

CHANGE_COLUMN_VALUE = """
mutation($board_id: ID!, $item_id: ID!, $column_id: String!, $value: JSON!) {
  change_column_value(
    board_id: $board_id
    item_id: $item_id
    column_id: $column_id
    value: $value
  ) {
    id
  }
}
"""
