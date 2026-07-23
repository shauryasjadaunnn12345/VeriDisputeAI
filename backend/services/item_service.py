from backend.models.item import Item

# Example in-memory store; swap for a real database in production.
_ITEMS: dict[int, Item] = {}


def list_items() -> list[Item]:
    return list(_ITEMS.values())


def get_item(item_id: int) -> Item | None:
    return _ITEMS.get(item_id)


def create_item(item: Item) -> Item:
    _ITEMS[item.id] = item
    return item
