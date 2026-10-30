import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .db import Base, SessionLocal, engine
from .models import Inventory, Product, ProductVariant


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "seed_catalog.json"


def seed_catalog(db: Session) -> None:
    """Insert the mock catalog only when the products table is empty."""
    existing = db.scalar(select(func.count()).select_from(Product))
    if existing:
        return
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for item in catalog:
        product = Product(
            name=item["name"], category=item["category"],
            description=item["description"], image_url=item["image_url"],
            aliases=item["aliases"],
        )
        for variant_data in item["variants"]:
            variant = ProductVariant(
                sku=variant_data["sku"],
                attributes=variant_data["attributes"],
                unit_price=variant_data["unit_price"],
                currency=variant_data.get("currency", "VND"),
            )
            variant.inventory = Inventory(
                available_quantity=variant_data["available_quantity"]
            )
            product.variants.append(variant)
        db.add(product)
    db.commit()


def initialize_database() -> None:
    """Create missing tables and seed the catalog using the configured database."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_catalog(db)


if __name__ == "__main__":
    initialize_database()
    print("SQLite schema is ready and mock catalog is seeded.")
