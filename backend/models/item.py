from pydantic import BaseModel


class Item(BaseModel):
    """Example data model."""

    id: int
    name: str
    description: str | None = None
