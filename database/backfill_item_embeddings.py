import logging
from typing import Optional, List

from scheduler_core.db import SessionLocal
from scheduler_core.models import Item, ItemEmbedding
from database.vectordb import VectorDB


logger = logging.getLogger(__name__)


def _build_item_content(item: Item) -> Optional[str]:
    """
    Build a text blob to embed for an item.
    Combines the most relevant textual fields into a single string.
    """
    parts: List[str] = []

    if item.name:
        parts.append(f"Name: {item.name}")
    if item.description:
        parts.append(f"Description: {item.description}")
    if item.comments:
        parts.append(f"Comments: {item.comments}")
    if item.remarks:
        parts.append(f"Remarks: {item.remarks}")
    if item.expression:
        parts.append(f"Expression: {item.expression}")
    if item.url:
        parts.append(f"URL: {item.url}")

    if not parts:
        return None

    return "\n".join(parts)


def backfill_item_embeddings() -> None:
    """
    For every item without existing embeddings, generate and insert embeddings
    into dbo.item_embeddings using VectorDB.add_document.
    """
    session = SessionLocal()
    vdb = VectorDB()

    try:
        # Only process items that don't have any embeddings yet to avoid duplicates.
        items = (
            session.query(Item)
            .outerjoin(ItemEmbedding, Item.id == ItemEmbedding.item_id)
            .filter(ItemEmbedding.id.is_(None))
            .all()
        )

        if not items:
            print("No items without embeddings found. Nothing to backfill.")
            return

        print(f"Backfilling embeddings for {len(items)} item(s)...")

        for item in items:
            content = _build_item_content(item)
            if not content:
                logger.warning(
                    "Skipping item id=%s because no textual content is available to embed.",
                    item.id,
                )
                continue

            print(f"  Embedding item id={item.id}, name={item.name!r}")
            try:
                vdb.add_document(item.id, content)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "Failed to create embeddings for item id=%s: %s", item.id, exc, exc_info=True
                )
                # Continue with other items rather than aborting the whole backfill
                continue

        print("Embedding backfill completed.")

    finally:
        session.close()


def main() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    backfill_item_embeddings()


if __name__ == "__main__":
    main()

