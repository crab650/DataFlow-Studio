---
trigger: always_on
---

# DataFlow Studio — 專案永久記憶與架構規範 (AI Agent Memory)

當使用者在此工作區開啟新對話時，請立即載入以下專案背景與架構記憶，並始終使用**繁體中文**與使用者溝通：

## 1. 平台定位與名稱
- **系統名稱**：`DataFlow Studio`（SQL + Python 專案制數據分析工作台）
- **啟動方式**：
  - 執行 `python app.py` 或雙擊 `start_DataFlow_Studio.bat`
  - 本地網址：`http://127.0.0.1:5000`
- **核心設計理念**：
  - 結合 **SQL 查詢**（SQLite 語法 + Chart.js 雙軸互動圖表）與 **Python (`df`) 模式**（Pandas / NumPy / Matplotlib / Seaborn / Scikit-Learn）的雙引擎數據探索與實戰教學平台。
  - 遵循 **「數據分析 4 步思考 SOP」**：
    - **Step 1 看目標 (Target)**：檢查主角變數比例與類別不平衡、空值、重複值。
    - **Step 2 篩選重點 (Filter)**：全表相關係數排行 (`|r| >= 0.1`) 與分組平均值對比。
    - **Step 3 找分界線 (Threshold)**：透過 SQL `CASE WHEN` + 雙軸圖（折線看比率、長條看樣本數）或 Python 箱型圖找轉折點。
    - **Step 4 規則驗證與建模 (Validate)**：多維度風險燈號歸因、決策樹自動切分點 (`DecisionTreeClassifier` / `DecisionTreeRegressor` 搭配 `pd.get_dummies` 避免字串轉浮點數錯誤)、隨機森林特徵重要性。

## 2. 乾淨的「一專案一資料夾」隔離架構
本系統嚴格採用**按專案資料夾完全隔離**的架構，避免不同專案的 CSV 與資料庫混雜：

1. **`datasets/<專案資料夾名稱>/`（原始 CSV / Excel 數據存放區）**
   - 每個分析專案都有自己獨立的子資料夾。
   - 目前預設示範專案為：`datasets/01_Manufacturing_Quality_ERP/`，內含工廠 ERP 多表關聯架構：
     - `production_orders_erp.csv` -> 匯入為資料表 `defects`（3,240 筆生產工單與不良率主表，含 `OrderID`, `SupplierID`, `MachineID`）
     - `supplier_master.csv` -> 匯入為資料表 `suppliers`（6 家供應商主檔）
     - `machine_master.csv` -> 匯入為資料表 `machines`（8 台產線機台主檔，跨一廠/二廠/三廠）
     - `manufacturing_defect_dataset.csv`（原始未擴充備份檔）
   - 使用者可隨時在 `datasets/` 下新增資料夾（例如 `datasets/02_Sales_Analytics/`）放入單個或多個 CSV，並點擊網頁頂端「🔄 掃描」(`POST /api/scan_folders`) 自動建庫並生成 11 則 SQL + Python 入門探索筆記。

2. **`system_data/<專案資料夾名稱>/`（系統資料庫與筆記隔離存放區）**
   - 每個專案資料夾在 `system_data/` 下都有同名子資料夾，內含 3 個完全獨立的檔案：
     - `workspace.db`：該專案專屬的 SQLite 資料庫（不同專案即使有同名表也 100% 互不覆蓋）。
     - `saved_queries.json`：該專案各資料表的 SQL / Python 儲存筆記與圖表設定。
     - `column_dictionary.json`：該專案各資料表的中英欄位對照與分析用途字典。

## 3. 已實作的重要功能清單（修改程式碼時請務必保留）
- **頂端三層導覽列**：`📁 專案資料夾` (`#headerFolderSelector`) + `🔄 掃描` -> `📄 資料表` (`#headerTableSelector`) -> `🎯 主角(Y)` (`#targetColSelector`)。
- **多檔匯入與多表關聯 (`🔗 多表關聯/合併`)**：
  - 支援單選或多選 `.csv` / `.xlsx` 匯入（可選「各自建表 `separate`」或「上下疊加 `concat`」）。
  - 支援視覺化左右關聯（SQL `JOIN` / Python `pd.merge`）與上下疊加（`UNION ALL` / `pd.concat`）。
  - Python 執行環境內建 `tables` 字典 (`LazyTablesDict`)，可直接寫 `tables['suppliers']`、`tables['machines']` 跨表呼叫同一專案內的任何資料表。
- **多表欄位字典**：
  - 左側邊欄「🗂️ 欄位字典」支援切換 `📚 全部表` 或單一資料表分組檢視。
  - 上方「🌐 中英欄位字典」彈窗支援分頁切換編輯專案內任一張表的中英對照，且查詢結果若包含 `JOIN` 跨表欄位會自動跨表查表翻譯。
- **高清大圖檢視器 (`#plotZoomModal`)**：
  - 點擊 Python 繪圖或 SQL 圖表放大按鈕，會開啟全螢幕 Lightbox（支援 50%~300% 縮放、PNG 下載，以及將 Base64 轉為 `Blob URL` 在新分頁打開，解決瀏覽器阻擋 `data:image` 頂層導覽的問題）。
- **側邊欄隨用彈出與釘住模式 (`Flyout / Pinned Drawer`)**：
  - 左側常駐極簡迷你 Dock（44px），支援「用時彈出、用完自動彈回縮起」模式，最大化代碼編輯與圖表展示空間；同時支援「📌 釘住 (Pin)」固定並排展開。
- **程式庫自訂分類資料夾與原生 Drag & Drop 拖曳**：
  - 支援使用者自訂新建資料夾分類（如「01_銷量趨勢」、「02_商品損益分析」），可一鍵展開/折疊所有資料夾。
  - 支援滑鼠按住程式卡片直接 **拖曳 (Drag & Drop)** 丟入目標資料夾，自動高亮提示並持久化存入 `saved_queries.json`。卡片亦提供下拉選單供快速移動。

## 4. README 分析數據專案清單維護規則

`README.md` 的「分析數據專案清單」以資料分析專案為單位，每個專案只佔一列。新增資料集專案才新增並編號；同一專案的 SQL、Python、筆記、欄位字典與資料表寫在該專案原列，不把平台功能、單一檔案或課程另列。數量變更時核對並更新原列。詳細規則見根目錄 `AGENTS.md`。

此清單也有英文版 `README.en.md`；任何新專案或數量變更都要同步更新兩份 README，並保留兩份文件頂端的語言切換連結。
