# DataFlow Studio

繁體中文 | [English](README.en.md)

**DataFlow Studio** 是一個在本機執行的 SQL 與 Python 資料分析工作台。它將每份資料按專案資料夾匯入獨立的 SQLite 資料庫，讓使用者在同一個網頁中探索欄位、執行查詢、使用 Pandas 分析、繪製圖表，並保存可重複執行的學習筆記。

這個專案以「邊做邊學」為主：先觀察資料與提出問題，再用 SQL 和 Python 驗證，最後把程式、結果判讀與限制記在筆記中。

## 主要功能

- **專案隔離**：每個 `datasets/<專案名稱>/` 對應一個 `system_data/<專案名稱>/workspace.db`，避免不同資料集的表格混在一起。
- **SQL 與 Python 雙模式**：SQL 使用 SQLite；Python 模式會把目前資料表載入為 Pandas `df`，並提供 `tables` 讀取同專案的其他表。
- **資料匯入與整理**：支援 CSV、Excel、資料夾掃描、多檔匯入，以及在介面中進行 JOIN／上下合併。
- **分析視覺化**：SQL 結果可製作雙軸圖；Python 可輸出 DataFrame、文字與 Matplotlib／Seaborn 圖表。
- **可保存的教學筆記**：每則筆記可保留程式碼、解說、分類與圖表設定；各專案另有中英欄位字典。

## 快速開始

已在 **Windows 與 Python 3.12** 環境使用。請先安裝 Python 套件：

```bash
python -m pip install -r requirements.txt
```

在專案根目錄啟動：

```bash
python app.py
```

或在 Windows 雙擊 `start_DataFlow_Studio.bat`。啟動後開啟 **http://127.0.0.1:5000**。網頁介面的 Tailwind CSS、Chart.js 和 CodeMirror 從 CDN 載入，因此初次開啟介面需要網路連線。

GitHub 版本保留示範 CSV、課程筆記與欄位字典；SQLite `workspace.db` 會在第一次啟動時由 CSV 重建，首次啟動可能需要稍等。

### 開始一次分析

1. 在頁面上方選擇**專案資料夾**與**資料表**。
2. 在左側查看欄位字典或選擇教學筆記；按「執行」或 `Ctrl+Enter`。
3. SQL 模式直接寫 SQLite 查詢。Python 模式可使用 `df`、`tables`、`pd`、`np`、`plt` 和 `sns`。
4. 在下方看表格或圖表，並把自己的觀察存成筆記。

例如選擇 Superstore 的 `superstoreorders` 表後，可執行：

```sql
SELECT category,
       COUNT(*) AS item_rows,
       ROUND(SUM(sales), 2) AS total_sales,
       ROUND(SUM(profit), 2) AS total_profit
FROM superstoreorders
GROUP BY category
ORDER BY total_sales DESC;
```

同一張表在 Python 模式可寫：

```python
df.groupby('category')[['sales', 'profit']].sum().round(2)
```

## 分析數據專案清單

這張表以**分析數據的專案**為單位：每個資料集專案只佔一列，該專案做過的 SQL、Python、筆記和資料字典都寫在同一列。

| 編號 | 分析專案 | 資料與分析內容 | 已完成的學習內容 | 入口／詳細說明 |
|---|---|---|---|---|
| 01 | 製造缺陷與示範 ERP | `defects` 3,240 筆，搭配供應商、機台共 3 張表；分析缺陷比例、風險條件與模型表現 | 10 則 SQL／Python 課程、32 個欄位解說 | 選 `01_Manufacturing_Quality_ERP` → `defects`；[課程說明](docs/manufacturing_defects_course.md) |
| 02 | Global Superstore 零售分析 | `superstoreorders` 51,290 筆；分析銷售、利潤、品類、地區與折扣 | 30 則 SQL／Python 筆記（含 8 則 ST1 入門練習）、21 個欄位解說 | 選 `02_Superstore_Sales` → `superstoreorders` |
| 03 | Olist 巴西電商多表分析 | 8 張核心表，訂單表 99,441 筆；分析訂單、顧客、商品、付款、評價與回購 | 12 則專題 SQL 課程（訂單表共 20 則筆記）、47 個欄位解說 | 選 `03_Olist_Brazilian_Ecommerce` → `olist_orders_dataset`；[課程說明](docs/olist_sql_course.md) |

**更新規則：** 以後每新增一個分析數據的專案，就在這張表增加一列並依序編號。平台功能、單一檔案、課程或欄位字典都屬於專案內容，不另外佔一列；已有專案新增分析成果時，更新該專案原有的列。這項規則也記在根目錄的 `AGENTS.md`。

## 加入自己的資料

**方法一：資料夾掃描。** 在 `datasets/` 下建立一個專案資料夾，放入一個或多個 `.csv`、`.xlsx` 或 `.xls` 檔，在頁面按「掃描」。系統會建立獨立 SQLite 資料庫與入門筆記。之後來源檔內容改變時，再掃描可更新對應資料表並保留既有筆記。既有資料庫首次建立來源指紋時，會保留原有表格修改。

**方法二：網頁匯入。** 使用頁面右上角「匯入數據」，可為單檔或多檔指定專案名稱，選擇各自建表或上下合併。

Olist 的八張核心表可使用 `python scripts/import_olist.py` 從[官方 Kaggle 資料集](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)重新取得並匯入；大型地理座標表未列入這套入門課程。課程筆記與欄位字典可分別由 `python olist_sql_lessons.py`、`python olist_column_dictionary.py` 補入，安裝程式會保留已有的編輯。

## 專案結構

```text
app.py                     Flask API、資料匯入、SQL／Python 執行與範本產生
templates/index.html       網頁工作台
datasets/                  各專案原始 CSV／Excel
system_data/               各專案 SQLite、筆記、欄位字典與來源指紋
learning_notes.py          製造缺陷課程內容
olist_sql_lessons.py        Olist SQL 課程內容
olist_column_dictionary.py Olist 中英欄位字典
scripts/import_olist.py    Olist 官方資料匯入程式
docs/                      課程說明
tests/                     資料安全與課程可執行性測試
```

匯入 Olist 資料後可執行測試：

```bash
python -m unittest discover -s tests -v
```

## 資料來源與使用範圍

- 製造缺陷原始 CSV 來自 [Predicting Manufacturing Defects Dataset](https://www.kaggle.com/datasets/rabieelkharoua/predicting-manufacturing-defects-dataset)。專案中的 `OrderID`、`SupplierID`、`MachineID` 與附屬主檔是教學用途的示範資料，並非原始資料集提供的真實 ERP 紀錄。
- Superstore 的 21 欄版本對應 [SuperStore Sales Analytics](https://www.kaggle.com/datasets/thuandao/superstore-sales-analytics)。
- Olist 資料來自 [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)；官方 Kaggle API 將其授權標示為 **CC BY-NC-SA 4.0**。來源及匯入範圍另記於 `datasets/03_Olist_Brazilian_Ecommerce/SOURCE.md`。

各資料夾的 `SOURCE.md` 記載資料來源與授權。儲存庫未宣告應用程式程式碼的開源授權；請分別遵守各資料集的授權條款。

本工具預設只監聽 `127.0.0.1`。Python 編輯器會執行使用者輸入的程式碼，適合在可信任的本機環境學習與分析；目前沒有帳號、權限控管或公開部署設定。示範資料中的分析關聯也不能直接當作因果結論。
