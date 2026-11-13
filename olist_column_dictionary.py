"""Bilingual field definitions for the eight imported Olist tables."""

import json
import os
import shutil
import sqlite3
from pathlib import Path


FIELDS = {
    "olist_orders_dataset": {
        "order_id": ("訂單編號", "每張訂單的唯一鍵；連結商品明細、付款與評價表。"),
        "customer_id": ("顧客資料編號", "連結顧客表；跨訂單辨識同一顧客請使用 customer_unique_id。"),
        "order_status": ("訂單狀態", "例如 delivered、canceled；分析收入或物流時先決定要包含哪些狀態。"),
        "order_purchase_timestamp": ("下單時間", "訂單建立時間；可用於月度訂單趨勢。"),
        "order_approved_at": ("付款核准時間", "訂單付款獲核准的時間；可能為空。"),
        "order_delivered_carrier_date": ("交給物流時間", "賣家將商品交給物流業者的時間；可能為空。"),
        "order_delivered_customer_date": ("實際送達時間", "顧客收到商品的時間；未送達訂單通常為空。"),
        "order_estimated_delivery_date": ("預計送達日期", "資料中的預計交貨日；可與實際送達日比較準時率。"),
    },
    "olist_customers_dataset": {
        "customer_id": ("顧客資料編號", "對應 orders.customer_id；在此資料中偏向訂單層級顧客資料。"),
        "customer_unique_id": ("顧客唯一識別碼", "跨訂單辨識同一顧客；計算回購顧客時使用。"),
        "customer_zip_code_prefix": ("顧客郵遞區號前綴", "收件地郵遞區號前綴；不是完整地址。"),
        "customer_city": ("顧客城市", "顧客所在地城市；分析買方地域分布。"),
        "customer_state": ("顧客州別", "顧客所在地州；不要與 seller_state 混淆。"),
    },
    "olist_order_items_dataset": {
        "order_id": ("訂單編號", "對應 orders.order_id；同一訂單可出現多筆商品明細。"),
        "order_item_id": ("訂單內明細序號", "同一 order_id 內的商品明細順序，單獨使用並非全表唯一鍵。"),
        "product_id": ("商品編號", "對應 products.product_id；用於查類別與商品屬性。"),
        "seller_id": ("賣家編號", "對應 sellers.seller_id；用於分析賣方地域。"),
        "shipping_limit_date": ("出貨期限", "賣家需完成出貨的期限；不是實際送達日。"),
        "price": ("商品明細價格", "該商品明細的售價；彙總後是商品銷售額，不等於利潤。"),
        "freight_value": ("明細運費", "該商品明細的運費；整張訂單需按 order_id 加總。"),
    },
    "olist_order_payments_dataset": {
        "order_id": ("訂單編號", "對應 orders.order_id；一張訂單可能有多筆付款紀錄。"),
        "payment_sequential": ("付款序號", "同一訂單內的付款順序。"),
        "payment_type": ("付款方式", "例如信用卡、boleto、voucher；一張訂單可混用付款方式。"),
        "payment_installments": ("分期數", "付款紀錄的分期次數。"),
        "payment_value": ("付款金額", "單筆付款紀錄金額；整單付款額需按 order_id 加總。"),
    },
    "olist_order_reviews_dataset": {
        "review_id": ("評價編號", "評價資料識別碼；分析訂單評價時仍須注意同單可能有多筆紀錄。"),
        "order_id": ("訂單編號", "對應 orders.order_id；可連結送達時間與評分。"),
        "review_score": ("評價分數", "顧客給的 1～5 分評價。"),
        "review_comment_title": ("評價標題", "顧客的文字標題；可能為空。"),
        "review_comment_message": ("評價內文", "顧客的文字內容；可能為空。"),
        "review_creation_date": ("評價建立日期", "評價建立時間。"),
        "review_answer_timestamp": ("評價填寫時間", "顧客提交評價答案的時間。"),
    },
    "olist_products_dataset": {
        "product_id": ("商品編號", "對應 order_items.product_id。"),
        "product_category_name": ("商品類別葡文名稱", "可連結類別翻譯表取得英文名稱；部分商品可能缺類別。"),
        "product_name_lenght": ("商品名稱長度", "商品名稱字元長度；原始資料欄名保留 lenght 拼字。"),
        "product_description_lenght": ("商品說明長度", "商品說明字元長度；原始資料欄名保留 lenght 拼字。"),
        "product_photos_qty": ("商品照片數", "商品頁面的照片張數。"),
        "product_weight_g": ("商品重量（克）", "商品重量，單位為克。"),
        "product_length_cm": ("商品長度（公分）", "商品尺寸長度，單位為公分。"),
        "product_height_cm": ("商品高度（公分）", "商品尺寸高度，單位為公分。"),
        "product_width_cm": ("商品寬度（公分）", "商品尺寸寬度，單位為公分。"),
    },
    "olist_sellers_dataset": {
        "seller_id": ("賣家編號", "對應 order_items.seller_id。"),
        "seller_zip_code_prefix": ("賣家郵遞區號前綴", "賣家所在地郵遞區號前綴。"),
        "seller_city": ("賣家城市", "賣家所在地城市；不是顧客收件城市。"),
        "seller_state": ("賣家州別", "賣家所在地州；不是顧客州別。"),
    },
    "product_category_name_translation": {
        "product_category_name": ("商品類別葡文名稱", "對應 products.product_category_name。"),
        "product_category_name_english": ("商品類別英文名稱", "翻譯後類別；若缺值，分析時可回退到葡文名稱。"),
    },
}


def install(dict_path, db_path):
    path = Path(dict_path)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(existing, dict):
        raise ValueError("欄位字典格式不正確")
    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        for table, fields in FIELDS.items():
            db_fields = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            if db_fields != set(fields):
                raise ValueError(f"{table} 欄位與預期不同：{db_fields ^ set(fields)}")
    finally:
        conn.close()
    added = 0
    for table, fields in FIELDS.items():
        table_dict = existing.setdefault(table, {})
        for column, (zh, purpose) in fields.items():
            if column not in table_dict:
                table_dict[column] = {"zh": zh, "purpose": purpose}
                added += 1
    if not added:
        return 0
    if path.exists() and not path.with_suffix(".json.bak").exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    pending = path.with_suffix(".json.tmp")
    pending.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(pending, path)
    return added


if __name__ == "__main__":
    project_dir = Path(__file__).parent / "system_data" / "03_Olist_Brazilian_Ecommerce"
    print(f"Installed {install(project_dir / 'column_dictionary.json', project_dir / 'workspace.db')} Olist field definitions")
