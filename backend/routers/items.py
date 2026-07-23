from fastapi import APIRouter, HTTPException

from backend.models.item import Item
from backend.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
def read_items() -> list[Item]:
    return item_service.list_items()


@router.get("/{item_id}")
def read_item(item_id: int) -> Item:
    item = item_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/")
def add_item(item: Item) -> Item:
    return item_service.create_item(item)
