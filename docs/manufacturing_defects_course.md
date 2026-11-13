# 製造缺陷：SQL + Python 實作課程

這份課程對應工作台的 `01_Manufacturing_Quality_ERP` 專案、`defects` 資料表。原始檔為 `datasets/01_Manufacturing_Quality_ERP/manufacturing_defect_dataset.csv`，共有 3,240 筆、17 欄。`DefectStatus` 是二元結果：1 表示有缺陷，0 表示無缺陷。這是[製造缺陷資料集](https://www.kaggle.com/datasets/rabieelkharoua/predicting-manufacturing-defects-dataset)，與機台預測維護資料集不同。

## 如何使用

1. 啟動 `python app.py` 或雙擊 `start_DataFlow_Studio.bat`。
2. 專案選 `01_Manufacturing_Quality_ERP`，資料表選 `defects`。
3. 在左側程式庫打開「📚 製造缺陷｜SQL + Python 實作課程」，依 01～10 順序選取筆記。
4. 按「執行」或 Ctrl+Enter。每則筆記的下方說明包含目的、結果判讀、語法重點、練習與限制。
5. 想保留自己的修改時，使用「另存新筆記」。課程程式碼中的 SQL 使用 SQLite 語法；Python 模式已提供 `df`、`pd`、`np`、`plt`、`sns`。

## 課程地圖

| 課次 | SQL／Python 配對 | 要回答的問題 | 主要技能 |
|---|---|---|---|
| 01–02 | 缺陷比例與資料體檢 | 整體基準線是多少？資料有缺值或重複嗎？ | `GROUP BY`、`value_counts`、缺值檢查 |
| 03–04 | 組間比較與分布 | 有缺陷組和無缺陷組的哪些指標不同？ | `AVG`、`groupby`、箱型圖 |
| 05–06 | 維護時數分段 | 風險是否在某段維護時數改變？樣本量夠嗎？ | `CASE WHEN`、`pd.cut`、Wilson 區間 |
| 07–08 | 風險訊號與規則指標 | 多個條件合用時，會標出多少樣本？誤報與漏報多少？ | CTE、布林條件、Precision／Recall |
| 09–10 | 混淆矩陣與留出測試 | 規則四格筆數是什麼？模型是否優於簡單基準？ | 二維 `GROUP BY`、Pipeline、訓練／測試切分 |

## 判讀範例

**先看基準線。** 此資料約 84% 的紀錄標為有缺陷。因此「全部判為有缺陷」也能得到約 84% 的準確率，單看 Accuracy 無法判斷模型有沒有實用價值。第 08 與 10 課會同時顯示 Precision、Recall、FP 與 FN。

**區分描述與預測。** 第 03～07 課用同一份資料尋找高風險條件，目的是描述樣本中的關聯。第 08～09 課在相同資料上評估規則，屬於教學演示。第 10 課才把資料留出 25% 做測試；即使如此，這仍是合成資料的內部測試，不代表真實工廠的未來表現。

**防止資料洩漏。** `DefectRate` 和 `QualityScore` 可能在產品檢驗後才產生。若要在生產前預測，必須確認預測當下是否已能取得這兩欄。第 10 課先把它們排除。此專案的 `OrderID`、`SupplierID`、`MachineID` 是平台依原始資料另外生成的示範 ERP 欄位，也沒有納入模型。`MaintenanceHours` 是否在決策時點已知，同樣要依實際流程判定。

**不要把關聯當成因果。** 高維護時數與高缺陷率一起出現，不表示維護導致缺陷；也可能是設備已有問題，才需要更多維護。這份原始資料沒有時間、班次或真實機台 ID，無法直接做可信的時序或機台層級驗證。

## 參考資料與改寫原則

- [Manufacturing Defect Risk Analysis](https://github.com/khanabu03/manufacturing-defect-risk-analysis)：提供基準 KPI、分段及風險組合的分析題材。原專案使用 SQL Server；本課程改成工作台可執行的 SQLite SQL。
- [Predicting Defect Rates in Manufacturing Using Machine Learning](https://github.com/TimvdHoek/Predicting-Defect-Rates-in-Manufacturing-Using-Machine-Learning)：提供從 EDA、特徵工程、切分到建模的學習順序。本課程的 Python 程式改為使用平台已載入的 `df`。

課程程式與詳細解說在 `learning_notes.py`，已安裝到 `system_data/01_Manufacturing_Quality_ERP/saved_queries.json`。再次執行 `python learning_notes.py` 只會補回缺少的課程筆記，不會覆蓋同 ID 的既有編輯。
