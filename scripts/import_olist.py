"""Import the official Olist CSVs into a separate DataFlow Studio project."""

import pathlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

PROJECT = "03_Olist_Brazilian_Ecommerce"
SOURCE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
FILES = (
    "olist_customers_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)


def main():
    archive = pathlib.Path(tempfile.gettempdir()) / "dataflow_olist_official.zip"
    if not archive.exists():
        urllib.request.urlretrieve(DOWNLOAD_URL, archive)
    target = pathlib.Path(app.DATASETS_DIR) / PROJECT
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        missing = set(FILES) - set(package.namelist())
        if missing:
            raise RuntimeError(f"Official archive is missing files: {sorted(missing)}")
        for name in FILES:
            destination = target / name
            if destination.exists():
                continue
            with package.open(name) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    (target / "SOURCE.md").write_text(
        "# Olist Brazilian E-Commerce Public Dataset\n\n"
        f"Official source: {SOURCE_URL}\n\n"
        "License reported by Kaggle API: CC BY-NC-SA 4.0.\n\n"
        "The large `olist_geolocation_dataset.csv` is deliberately omitted from this "
        "beginner SQL project. The eight included files preserve the core order, "
        "customer, item, payment, review, product, seller, and category relationships.\n",
        encoding="utf-8",
    )
    imported, errors = app.scan_datasets_folders()
    if errors:
        raise RuntimeError("Import errors: " + "; ".join(errors))
    print(f"Project: {PROJECT}")
    print(f"Imported tables: {[table for folder, table in imported if folder == PROJECT]}")
    conn = app.get_db_connection(PROJECT)
    try:
        indexes = (
            ("olist_orders_dataset", "order_id"),
            ("olist_orders_dataset", "customer_id"),
            ("olist_customers_dataset", "customer_id"),
            ("olist_order_items_dataset", "order_id"),
            ("olist_order_items_dataset", "product_id"),
            ("olist_order_items_dataset", "seller_id"),
            ("olist_order_payments_dataset", "order_id"),
            ("olist_order_reviews_dataset", "order_id"),
            ("olist_products_dataset", "product_id"),
            ("olist_sellers_dataset", "seller_id"),
            ("product_category_name_translation", "product_category_name"),
        )
        for table, column in indexes:
            conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_{column}" ON "{table}" ("{column}")')
        conn.commit()
        for name in FILES:
            table = pathlib.Path(name).stem
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(f"{table}: {count:,} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
