"""SQLite lessons for the official Olist data in DataFlow Studio."""

import json
import os
import shutil
from pathlib import Path


def lesson(number, title, sql, explanation, chart=None):
    return {
        "id": f"note_olist_sql_{number:02d}",
        "lang": "sql",
        "title": f"SQL {number:02d}｜{title}",
        "step_tag": "Olist SQL 多表實作",
        "folder": "📚 Olist｜SQL 多表分析練習",
        "sql": sql.strip(),
        "note": explanation.strip(),
        "chart_config": chart or {},
    }


OLIST_SQL_LESSONS = [
    lesson(1, "從訂單明細開始讀資料", """
SELECT order_id, customer_id, order_status,
       order_purchase_timestamp, order_delivered_customer_date
FROM olist_orders_dataset
ORDER BY order_purchase_timestamp
LIMIT 20;
""", """
目標：熟悉 SELECT、FROM、ORDER BY 與 LIMIT，認清一列代表一張訂單。
讀結果：order_id 是訂單鍵；customer_id 可連到顧客表。日期以文字格式儲存，格式為 YYYY-MM-DD HH:MM:SS，因此 SQLite 的 date()、strftime() 可解析。
動手改：把 LIMIT 20 改為 50；將排序改成 DESC，看最新訂單。
檢查：部分訂單沒有實際送達日期，這是未送達或取消等狀態；不要直接當作資料損壞。
"""),

    lesson(2, "訂單狀態與百分比分母", """
SELECT order_status AS 訂單狀態,
       COUNT(*) AS 訂單數,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM olist_orders_dataset), 2) AS 佔全部訂單百分比
FROM olist_orders_dataset
GROUP BY order_status
ORDER BY 訂單數 DESC;
""", """
目標：用 GROUP BY 算各狀態的訂單數，並明確寫出百分比的分母。
讀結果：delivered 是已送達，canceled 是取消；所有狀態的訂單數加總應為 99,441。這裡分母是全部訂單，因此各狀態百分比約加總為 100%。
語法：COUNT(*) 計算每組筆數；100.0 讓除法保留小數；子查詢提供全表總數。
動手改：增加 WHERE order_status <> 'delivered'，注意原查詢的分母仍是全部訂單。若想算「未送達各狀態內部佔比」，分母也要一起改。
""", {"type": "bar", "x_col": "訂單狀態", "y1_col": "訂單數", "y2_col": "佔全部訂單百分比"}),

    lesson(3, "月度訂單趨勢", """
SELECT strftime('%Y-%m', order_purchase_timestamp) AS 訂購月份,
       COUNT(*) AS 訂單數,
       SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) AS 已送達數
FROM olist_orders_dataset
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY strftime('%Y-%m', order_purchase_timestamp)
ORDER BY 訂購月份;
""", """
目標：用日期分組與條件計數看訂單量變化。
讀結果：訂單數包含所有狀態；已送達數只數 delivered。兩條線的差距反映資料截取時還未送達、取消等情形，不能直接當作物流失敗率。
語法：strftime('%Y-%m', 日期) 取得月份；SUM(CASE WHEN ...) 是條件計數。
動手改：WHERE 限制在 2017-01 到 2018-08 的完整月份，再看趨勢。資料首尾月份不完整，不宜直接比較月增率。
""", {"type": "bar_line", "x_col": "訂購月份", "y1_col": "訂單數", "y2_col": "已送達數"}),

    lesson(4, "交貨時間與準時率", """
SELECT strftime('%Y-%m', order_purchase_timestamp) AS 訂購月份,
       COUNT(*) AS 已送達訂單數,
       ROUND(AVG(julianday(order_delivered_customer_date) -
                 julianday(order_purchase_timestamp)), 2) AS 平均交貨天數,
       ROUND(AVG(CASE WHEN date(order_delivered_customer_date) <= date(order_estimated_delivery_date)
                      THEN 1.0 ELSE 0.0 END) * 100, 2) AS 準時率百分比
FROM olist_orders_dataset
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL
GROUP BY strftime('%Y-%m', order_purchase_timestamp)
ORDER BY 訂購月份;
""", """
目標：練習日期相減、條件比例與 WHERE 過濾。
讀結果：平均交貨天數從購買到實際送達；準時率比較「送達日」與「預計送達日」。結果只含已送達且兩個日期完整的訂單。
語法：SQLite 的 julianday() 差值單位為天；date() 忽略時分秒，適合用日期判斷是否準時。
動手改：改成 GROUP BY 顧客州別，需先 JOIN 顧客表，並看每州樣本數。
提醒：預計送達日是資料中的承諾日期，不等同全公司的統一服務標準。
""", {"type": "bar_line", "x_col": "訂購月份", "y1_col": "平均交貨天數", "y2_col": "已送達訂單數"}),

    lesson(5, "JOIN 顧客表看州別訂單", """
SELECT c.customer_state AS 顧客州別,
       COUNT(*) AS 訂單數,
       COUNT(DISTINCT c.customer_unique_id) AS 不重複顧客數
FROM olist_orders_dataset AS o
JOIN olist_customers_dataset AS c ON o.customer_id = c.customer_id
GROUP BY c.customer_state
ORDER BY 訂單數 DESC
LIMIT 15;
""", """
目標：學第一個一對一 JOIN，並區分「訂單數」與「不重複顧客數」。
關聯：orders.customer_id → customers.customer_id；customer_unique_id 才用來辨識跨訂單的同一顧客。
讀結果：顧客州別指收件顧客，不是賣家所在地。各州訂單數相加應接近訂單表筆數；若不符，檢查 JOIN 缺鍵。
動手改：改成按 customer_state 排序，觀察各州訂單數落差；再試 COUNT(DISTINCT o.order_id) 核對訂單數。
""", {"type": "bar", "x_col": "顧客州別", "y1_col": "訂單數", "y2_col": "不重複顧客數"}),

    lesson(6, "訂單商品金額與運費", """
SELECT o.order_id AS 訂單編號,
       COUNT(*) AS 商品明細列數,
       ROUND(SUM(i.price), 2) AS 商品小計,
       ROUND(SUM(i.freight_value), 2) AS 運費合計,
       ROUND(SUM(i.price + i.freight_value), 2) AS 商品加運費
FROM olist_orders_dataset AS o
JOIN olist_order_items_dataset AS i ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
GROUP BY o.order_id
ORDER BY 商品加運費 DESC
LIMIT 20;
""", """
目標：理解一筆訂單可有多筆商品明細；先回到每單一列，再比較金額。
關聯：orders.order_id → order_items.order_id。一筆明細的 price 是該明細價格，freight_value 是其運費；SUM 後才得到整單小計。
讀結果：商品明細列數大於 1 的訂單，不能直接從單筆明細推估整單金額。
動手改：移除 LIMIT，將 ORDER BY 改成商品明細列數 DESC，觀察多商品訂單。
提醒：這是商品與運費的加總，不包含退款或平台成本，也不是利潤。
"""),

    lesson(7, "商品類別銷售排行", """
SELECT COALESCE(t.product_category_name_english,
                p.product_category_name, 'unknown') AS 商品類別,
       COUNT(*) AS 明細列數,
       ROUND(SUM(i.price), 2) AS 商品銷售額
FROM olist_order_items_dataset AS i
JOIN olist_orders_dataset AS o ON i.order_id = o.order_id
JOIN olist_products_dataset AS p ON i.product_id = p.product_id
LEFT JOIN product_category_name_translation AS t
       ON p.product_category_name = t.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
ORDER BY 商品銷售額 DESC
LIMIT 15;
""", """
目標：串接訂單、明細、商品與類別翻譯四張表，回答哪些類別的商品銷售額最高。
關聯：items.product_id → products.product_id；products.product_category_name → translation.product_category_name。
語法：LEFT JOIN 保留沒有翻譯的商品；COALESCE 依序取英文、葡文或 unknown。
讀結果：SUM(price) 是已送達商品明細的價格，不含運費。COUNT(*) 是明細列數，不是訂單數；若要訂單數，使用 COUNT(DISTINCT i.order_id)。
動手改：同時顯示 COUNT(DISTINCT i.order_id)，比較「明細列數」與「訂單數」。
""", {"type": "bar", "x_col": "商品類別", "y1_col": "商品銷售額", "y2_col": "明細列數"}),

    lesson(8, "付款方式：一列不是一張訂單", """
SELECT payment_type AS 付款方式,
       COUNT(*) AS 付款紀錄數,
       COUNT(DISTINCT order_id) AS 涉及訂單數,
       ROUND(SUM(payment_value), 2) AS 付款總額
FROM olist_order_payments_dataset
GROUP BY payment_type
ORDER BY 付款總額 DESC;
""", """
目標：辨認資料粒度。付款表一列是一筆付款紀錄，同一訂單可能有多筆付款。
讀結果：付款紀錄數與涉及訂單數不同，說明不能用 COUNT(*) 直接說有多少張訂單。不同付款方式的涉及訂單數相加，也可能高於全體訂單數，因為一張訂單可用多種付款方式。
語法：COUNT(DISTINCT order_id) 在每組內去除重複訂單；SUM(payment_value) 計付款金額。
動手改：加入 AVG(payment_value)，比較每筆付款紀錄平均金額。它不是平均訂單金額。
""", {"type": "bar", "x_col": "付款方式", "y1_col": "付款總額", "y2_col": "涉及訂單數"}),

    lesson(9, "先彙總再 JOIN：避免金額膨脹", """
WITH item_totals AS (
    SELECT order_id, SUM(price) AS 商品小計, SUM(freight_value) AS 運費
    FROM olist_order_items_dataset GROUP BY order_id
), payment_totals AS (
    SELECT order_id, SUM(payment_value) AS 付款合計
    FROM olist_order_payments_dataset GROUP BY order_id
)
SELECT o.order_id AS 訂單編號,
       ROUND(i.商品小計 + i.運費, 2) AS 商品加運費,
       ROUND(p.付款合計, 2) AS 付款合計,
       ROUND(p.付款合計 - i.商品小計 - i.運費, 2) AS 金額差
FROM olist_orders_dataset AS o
JOIN item_totals AS i ON o.order_id = i.order_id
JOIN payment_totals AS p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered'
ORDER BY ABS(p.付款合計 - i.商品小計 - i.運費) DESC
LIMIT 20;
""", """
目標：學會多張一對多表的安全 JOIN。items 和 payments 都可能對同一 order_id 有多列；直接把兩張明細表 JOIN，會產生相乘列數並重複計算金額。
方法：兩個 CTE 各先 GROUP BY order_id，變成每單一列，再 JOIN 訂單表。
讀結果：金額差用來核對付款與商品加運費；若有差異，要再查訂單狀態、資料缺漏或業務規則，不能直接叫作利潤。
動手改：在 item_totals 與 payment_totals 加 COUNT(*)，找出多商品且多次付款的訂單；再試原始明細直接 JOIN，比較列數如何膨脹。
"""),

    lesson(10, "評價分數與交貨延遲", """
WITH review_by_order AS (
    SELECT order_id, AVG(review_score) AS 平均評分
    FROM olist_order_reviews_dataset
    GROUP BY order_id
), delivery AS (
    SELECT o.order_id,
           CASE WHEN date(o.order_delivered_customer_date) > date(o.order_estimated_delivery_date)
                THEN '晚到' ELSE '準時或提早' END AS 交貨類別,
           r.平均評分
    FROM olist_orders_dataset AS o
    JOIN review_by_order AS r ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT 交貨類別, COUNT(*) AS 有評價訂單數,
       ROUND(AVG(平均評分), 2) AS 平均評價分數
FROM delivery
GROUP BY 交貨類別
ORDER BY 交貨類別;
""", """
目標：練習先處理可能重複的評價，再比較準時與晚到訂單的分數。
方法：review_by_order 先變成每單一列；交貨類別只對已送達且日期完整的訂單判定。
讀結果：每組的「有評價訂單數」是有評價且符合條件的訂單，不是所有訂單；平均評價分數是 1～5 分。
動手改：增加按顧客州別分組，但先確認每組樣本數，避免小樣本被誤讀。
提醒：晚到與低分若同時出現，只能說有關聯；不能從觀察資料直接證明晚到是唯一原因。
"""),

    lesson(11, "賣家州別與商品銷售額", """
SELECT s.seller_state AS 賣家州別,
       COUNT(DISTINCT i.seller_id) AS 賣家數,
       COUNT(*) AS 商品明細列數,
       ROUND(SUM(i.price), 2) AS 商品銷售額
FROM olist_order_items_dataset AS i
JOIN olist_sellers_dataset AS s ON i.seller_id = s.seller_id
JOIN olist_orders_dataset AS o ON i.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY s.seller_state
ORDER BY 商品銷售額 DESC
LIMIT 15;
""", """
目標：從商品明細連到賣家表，練習辨認賣家所在地與顧客所在地。
讀結果：賣家數是州內不同 seller_id 的數量；商品銷售額是已送達明細的 SUM(price)。這不是州內居民的消費額，也不是賣家淨收入。
語法：COUNT(DISTINCT i.seller_id) 防止同一賣家多筆商品被重複算成多個賣家。
動手改：與第 5 課顧客州別訂單量比較，看看買方與賣方地理分布是否不同。
""", {"type": "bar", "x_col": "賣家州別", "y1_col": "商品銷售額", "y2_col": "賣家數"}),

    lesson(12, "回購顧客排行與視窗函數", """
WITH orders_per_customer AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS 訂單數,
           ROUND(SUM(i.price), 2) AS 商品消費額
    FROM olist_customers_dataset AS c
    JOIN olist_orders_dataset AS o ON c.customer_id = o.customer_id
    JOIN olist_order_items_dataset AS i ON o.order_id = i.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT ROW_NUMBER() OVER (ORDER BY 商品消費額 DESC) AS 名次,
       customer_unique_id AS 顧客唯一編號,
       訂單數, 商品消費額
FROM orders_per_customer
WHERE 訂單數 >= 2
ORDER BY 商品消費額 DESC
LIMIT 20;
""", """
目標：以 customer_unique_id 辨識跨訂單顧客，找出有回購的顧客並練習視窗函數。
關聯：customers.customer_id → orders.customer_id → items.order_id。customer_id 在這份資料中對應訂單層級的顧客資料；跨訂單識別要用 customer_unique_id。
語法：COUNT(DISTINCT o.order_id) 算訂單數，SUM(i.price) 算商品消費額；ROW_NUMBER() 依消費額給名次。
讀結果：只顯示訂單數至少 2 的顧客；商品消費額不含運費、退款或成本。
動手改：把至少 2 單改成至少 3 單，看回購顧客數與排行如何變化。
"""),
]


def install(notes_path):
    path = Path(notes_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    key = "olist_orders_dataset"
    existing = data.get(key, [])
    if not isinstance(existing, list):
        raise ValueError("orders 筆記格式不正確")
    ids = {n.get("id") for n in existing if isinstance(n, dict)}
    additions = [n for n in OLIST_SQL_LESSONS if n["id"] not in ids]
    if not additions:
        return 0
    backup = path.with_suffix(".json.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    data[key] = existing + additions
    pending = path.with_suffix(".json.tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(pending, path)
    return len(additions)


if __name__ == "__main__":
    target = Path(__file__).parent / "system_data" / "03_Olist_Brazilian_Ecommerce" / "saved_queries.json"
    print(f"Installed {install(target)} Olist SQL lessons")
