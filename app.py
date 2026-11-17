import os
import io
import ast
import json
import base64
import traceback
import contextlib
import sqlite3
import hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, render_template, request, jsonify

# 設定 Matplotlib 中文字型，避免圖表中文變方框
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DATA_DIR = os.path.join(BASE_DIR, "system_data")
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
DEFAULT_PROJECT_FOLDER = "01_Manufacturing_Quality_ERP"
DEFAULT_PROJECT_DIR = os.path.join(DATASETS_DIR, DEFAULT_PROJECT_FOLDER)

os.makedirs(SYSTEM_DATA_DIR, exist_ok=True)
os.makedirs(DEFAULT_PROJECT_DIR, exist_ok=True)

DB_PATH = os.path.join(SYSTEM_DATA_DIR, "analysis_workspace.db")
NOTES_PATH = os.path.join(SYSTEM_DATA_DIR, "saved_queries.json")
COL_DICT_PATH = os.path.join(SYSTEM_DATA_DIR, "column_dictionary.json")
TABLE_FOLDERS_PATH = os.path.join(SYSTEM_DATA_DIR, "table_folders.json")
DEFAULT_CSV = os.path.join(DEFAULT_PROJECT_DIR, "manufacturing_defect_dataset.csv")

# 預設 defects 專案的中英欄位對照與分析用途字典
DEFAULT_DEFECTS_COL_DICT = {
    "OrderID": {"zh": "工單批號", "purpose": "唯一識別每筆生產工單紀錄"},
    "SupplierID": {"zh": "供應商代碼", "purpose": "關聯供應商主檔 (suppliers)"},
    "MachineID": {"zh": "機台編號", "purpose": "關聯產線機台主檔 (machines)"},
    "ProductionVolume": {"zh": "每日生產量", "purpose": "了解產量規模"},
    "ProductionCost": {"zh": "生產總成本", "purpose": "評估批次生產成本規模"},
    "SupplierQuality": {"zh": "供應商品質評分", "purpose": "分析來料品質"},
    "DeliveryDelay": {"zh": "交貨延遲天數", "purpose": "評估供應鏈交期準時率"},
    "DefectRate": {"zh": "每千件不良數", "purpose": "衡量品質"},
    "QualityScore": {"zh": "品質評分", "purpose": "比較品質表現"},
    "MaintenanceHours": {"zh": "每週維護時數", "purpose": "分析維護與品質的關係"},
    "DowntimePercentage": {"zh": "停機時間百分比", "purpose": "了解設備停機情況"},
    "InventoryTurnover": {"zh": "庫存周轉率", "purpose": "衡量庫存流動效率"},
    "StockoutRate": {"zh": "缺貨率", "purpose": "衡量原物料斷料或缺貨風險"},
    "WorkerProductivity": {"zh": "人員生產力", "purpose": "分析生產效率"},
    "SafetyIncidents": {"zh": "工安事故次數", "purpose": "監控車間作業安全紀錄"},
    "EnergyConsumption": {"zh": "能源消耗量", "purpose": "監控生產批次總能耗"},
    "EnergyEfficiency": {"zh": "能源使用效率", "purpose": "衡量設備節能表現"},
    "AdditiveProcessTime": {"zh": "積層加工時間", "purpose": "分析特殊製程耗時"},
    "AdditiveMaterialCost": {"zh": "積層材料成本", "purpose": "分析特殊製程耗材成本"},
    "DefectStatus": {"zh": "高低不良狀態", "purpose": "品質分類"}
}

DEFAULT_SUPPLIERS_COL_DICT = {
    "SupplierID": {"zh": "供應商代碼", "purpose": "與主表 defects 關聯的主鍵"},
    "SupplierName": {"zh": "供應商名稱", "purpose": "識別原料供應廠商"},
    "MaterialCategory": {"zh": "供應原料類別", "purpose": "分析不同原料種類對品質影響"},
    "Region": {"zh": "產地國別/地區", "purpose": "比較各產地供應鏈表現"},
    "ContractTier": {"zh": "合約等級", "purpose": "比較一級/二級/三級廠商來料表現"},
    "LeadTimeDays": {"zh": "標準交期天數", "purpose": "評估供應商標準供貨週期"}
}

DEFAULT_MACHINES_COL_DICT = {
    "MachineID": {"zh": "機台編號", "purpose": "與主表 defects 關聯的主鍵"},
    "MachineName": {"zh": "機台名稱", "purpose": "識別生產線設備"},
    "PlantArea": {"zh": "所屬廠區", "purpose": "比較一廠/二廠/三廠整體良率差異"},
    "MachineModel": {"zh": "設備機型", "purpose": "分析不同世代機型的穩定度"},
    "InstallYear": {"zh": "啟用年份", "purpose": "分析機齡老舊程度與維護時數關係"},
    "MaxCapacity": {"zh": "額定日產能上限", "purpose": "對照實際每日生產量是否超載"}
}

# 針對預設製造業缺陷數據 (defects) 的 15 條精選深度教學筆記
DEFECTS_DEFAULT_QUERIES = [
    {
        "id": "step1_target_ratio",
        "lang": "sql",
        "title": "【Step 1 看主角】檢查 DefectStatus 正常與異常比例",
        "step_tag": "Step 1: 看目標 (Target)",
        "sql": """-- 檢查目標變數 DefectStatus 的好壞品筆數與佔比
SELECT 
    CASE WHEN DefectStatus = 1 THEN '1 - 異常 (有缺陷)' ELSE '0 - 正常 (無缺陷)' END AS 狀態分類,
    COUNT(*) AS 筆數,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM defects), 2) AS 佔比百分比
FROM defects
GROUP BY DefectStatus
ORDER BY DefectStatus;""",
        "note": "💡 【分析思維 Step 1】拿到資料第一步永遠先看「主角 (目標變數 Y)」的分佈：\n1. 這裡發現異常 (1) 高達 84.04%（2,723 筆），正常 (0) 只有 15.96%（517 筆）。\n2. 結論：資料存在明顯的「類別不平衡」。後續看任何特徵時，如果某個區間的異常率也是 84% 左右，代表該區間只是平均水準；要找到異常率衝上 95%~99% 或掉到 10% 以下的區間，才是真正的關鍵分界線！",
        "chart_config": {
            "type": "bar",
            "x_col": "狀態分類",
            "y1_col": "筆數",
            "y2_col": "佔比百分比"
        }
    },
    {
        "id": "step2_group_means",
        "lang": "sql",
        "title": "【Step 2 全表比較】正常(0) vs 異常(1) 的關鍵指標平均值對比",
        "step_tag": "Step 2: 篩選重點 (Filter)",
        "sql": """-- 比較正常組(0)與異常組(1)在各欄位的平均值差異
SELECT 
    CASE WHEN DefectStatus = 1 THEN '1 - 異常組' ELSE '0 - 正常組' END AS 狀態分組,
    COUNT(*) AS 樣本數,
    ROUND(AVG(MaintenanceHours), 2) AS 平均維護時數,
    ROUND(AVG(DefectRate), 2) AS 平均製程缺陷率,
    ROUND(AVG(QualityScore), 2) AS 平均品質評分,
    ROUND(AVG(ProductionVolume), 1) AS 平均生產量,
    ROUND(AVG(DeliveryDelay), 2) AS 平均交貨延遲_無關對照,
    ROUND(AVG(SafetyIncidents), 2) AS 平均安全事故_無關對照
FROM defects
GROUP BY DefectStatus;""",
        "note": "💡 【分析思維 Step 2】為什麼要跑這條 SQL？\n當欄位很多時，用 `GROUP BY DefectStatus` 看好品與壞品的平均值差異：\n1. 有明顯差異的 4 個欄位：`平均維護時數` (6.79 vs 12.37)、`平均製程缺陷率` (2.01 vs 2.89)、`平均品質評分` (85.44 vs 79.13)、`平均生產量` (470.9 vs 563.3)。\n2. 幾乎沒差異的欄位（如交貨延遲、安全事故）：代表這些是干擾項，後續畫圖可以直接略過！",
        "chart_config": {
            "type": "grouped_bar",
            "x_col": "狀態分組",
            "y1_col": "平均維護時數",
            "y2_col": "平均品質評分"
        }
    },
    {
        "id": "step3_maintenance_hours",
        "lang": "sql",
        "title": "【Step 3 找分界線 A】維護時數 (MaintenanceHours) 幾小時以上會異常？",
        "step_tag": "Step 3: 找分界線 (Threshold)",
        "sql": """-- 觀察每個維護時數 (0~23小時) 的總筆數與異常率變化
SELECT 
    MaintenanceHours AS 維護時數,
    COUNT(*) AS 總筆數,
    SUM(DefectStatus) AS 異常筆數,
    ROUND(AVG(DefectStatus) * 100.0, 1) AS 異常率百分比
FROM defects
GROUP BY MaintenanceHours
ORDER BY MaintenanceHours;""",
        "note": "💡 【分析思維 Step 3-A】針對排名第一的特徵 `MaintenanceHours` (0~23 小時)，我們看每個小時的「異常率百分比」：\n1. 在 0 ~ 10 小時之間，異常率大約在 68% ~ 76% 之間波動。\n2. 一旦跨越 **10 小時（從 11 小時開始到 23 小時）**，異常率瞬間跳升並維持在 **94% ~ 98%**！\n3. 🎯 找到第 1 條黃金規則：`MaintenanceHours > 10`！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "維護時數",
            "y1_col": "異常率百分比",
            "y2_col": "總筆數"
        }
    },
    {
        "id": "step3_defect_rate_buckets",
        "lang": "sql",
        "title": "【Step 3 找分界線 B】製程缺陷率 (DefectRate) 分段異常率探索",
        "step_tag": "Step 3: 找分界線 (Threshold)",
        "sql": """-- 將連續小數 DefectRate (0.5~5.0) 每 0.5 切成一個區間
SELECT 
    CASE 
        WHEN DefectRate < 1.0 THEN '1) 0.5 ~ 1.0'
        WHEN DefectRate < 1.5 THEN '2) 1.0 ~ 1.5'
        WHEN DefectRate < 2.0 THEN '3) 1.5 ~ 2.0'
        WHEN DefectRate < 2.5 THEN '4) 2.0 ~ 2.5'
        WHEN DefectRate < 3.0 THEN '5) 2.5 ~ 3.0'
        WHEN DefectRate < 3.5 THEN '6) 3.0 ~ 3.5 (突破臨界!)'
        WHEN DefectRate < 4.0 THEN '7) 3.5 ~ 4.0'
        WHEN DefectRate < 4.5 THEN '8) 4.0 ~ 4.5'
        ELSE '9) 4.5 ~ 5.0'
    END AS 缺陷率區間,
    COUNT(*) AS 總筆數,
    ROUND(AVG(DefectStatus) * 100.0, 1) AS 異常率百分比
FROM defects
GROUP BY 缺陷率區間
ORDER BY 缺陷率區間;""",
        "note": "💡 【分析思維 Step 3-B】遇到連續小數（如 `DefectRate` 0.5~5.0）怎麼畫圖？\n用 `CASE WHEN` 把連續數值「切區間 (Binning)」：\n1. 在 `DefectRate < 3.0` 的前 5 個區間，異常率都落在 73% ~ 77%。\n2. 一旦進入 `3.0 ~ 3.5` 以上的區間，異常率立刻飆升到 **95.5% ~ 96.7%**！\n3. 🎯 找到第 2 條黃金規則：`DefectRate > 3.0`！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "缺陷率區間",
            "y1_col": "異常率百分比",
            "y2_col": "總筆數"
        }
    },
    {
        "id": "step3_quality_and_volume",
        "lang": "sql",
        "title": "【Step 3 找分界線 C】品質評分 (QualityScore) 分段異常率探索",
        "step_tag": "Step 3: 找分界線 (Threshold)",
        "sql": """-- 將品質分數 QualityScore (60~100分) 每 5 分切一個區間
SELECT 
    CASE 
        WHEN QualityScore < 65 THEN '1) 60~65分 (極低)'
        WHEN QualityScore < 70 THEN '2) 65~70分 (偏低)'
        WHEN QualityScore < 75 THEN '3) 70~75分 (臨界區)'
        WHEN QualityScore < 80 THEN '4) 75~80分 (正常)'
        WHEN QualityScore < 85 THEN '5) 80~85分 (正常)'
        WHEN QualityScore < 90 THEN '6) 85~90分 (良好)'
        WHEN QualityScore < 95 THEN '7) 90~95分 (優良)'
        ELSE '8) 95~100分 (頂尖)'
    END AS 品質分數區間,
    COUNT(*) AS 總筆數,
    ROUND(AVG(DefectStatus) * 100.0, 1) AS 異常率百分比
FROM defects
GROUP BY 品質分數區間
ORDER BY 品質分數區間;""",
        "note": "💡 【分析思維 Step 3-C】同樣用區間切分法觀察 `QualityScore` (60~100 分)：\n1. 當品質分數在 **75 分以下**（前三個區間 60~75 分），異常率高達 **95.3% ~ 96.6%**。\n2. 當品質分數 **>= 75 分** 後，異常率立刻降回 76% ~ 79%。\n3. 🎯 找到第 3 條黃金規則：`QualityScore < 75`！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "品質分數區間",
            "y1_col": "異常率百分比",
            "y2_col": "總筆數"
        }
    },
    {
        "id": "step3_production_volume",
        "lang": "sql",
        "title": "【Step 3 找分界線 D】生產量 (ProductionVolume) 每百件分段異常率",
        "step_tag": "Step 3: 找分界線 (Threshold)",
        "sql": """-- 驗證第 4 個關鍵特徵 ProductionVolume (100~999 件)
SELECT 
    CASE 
        WHEN ProductionVolume <= 200 THEN '1) 100~200'
        WHEN ProductionVolume <= 300 THEN '2) 201~300'
        WHEN ProductionVolume <= 400 THEN '3) 301~400'
        WHEN ProductionVolume <= 500 THEN '4) 401~500'
        WHEN ProductionVolume <= 600 THEN '5) 501~600'
        WHEN ProductionVolume <= 700 THEN '6) 601~700'
        WHEN ProductionVolume <= 800 THEN '7) 701~800'
        WHEN ProductionVolume <= 900 THEN '8) 801~900 (高產量臨界!)'
        ELSE '9) 901~999 (極高產量!)'
    END AS 生產量區間,
    COUNT(*) AS 總筆數,
    ROUND(AVG(DefectStatus) * 100.0, 1) AS 異常率百分比
FROM defects
GROUP BY 生產量區間
ORDER BY 生產量區間;""",
        "note": "💡 【分析思維 Step 3-D】驗證第 4 個關鍵特徵 `ProductionVolume` (100~999 件)：\n1. 在 100 ~ 800 件的前 7 個區間，異常率一直穩定在 78.5% ~ 84.2% 之間。\n2. 一旦生產量突破 **800 件**（801~999 件），異常率立刻跳升至 **95.5% ~ 97.8%**！\n3. 🎯 找到第 4 條黃金規則：`ProductionVolume > 800`！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "生產量區間",
            "y1_col": "異常率百分比",
            "y2_col": "總筆數"
        }
    },
    {
        "id": "step4_combined_rule",
        "lang": "sql",
        "title": "【Step 4 綜合驗證】組合 4 大黃金規則的預警準確率檢驗",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """-- 驗證 4 大條件 OR 組合規則的準確率
SELECT 
    CASE 
        WHEN (MaintenanceHours > 10 OR DefectRate > 3.0 OR QualityScore < 75 OR ProductionVolume > 800)
        THEN '觸發預警規則 (預測=1)'
        ELSE '未觸發規則 (預測=0)'
    END AS 規則判定結果,
    COUNT(*) AS 總筆數,
    SUM(CASE WHEN DefectStatus = 1 THEN 1 ELSE 0 END) AS 實際異常_1,
    SUM(CASE WHEN DefectStatus = 0 THEN 1 ELSE 0 END) AS 實際正常_0,
    ROUND(AVG(DefectStatus) * 100.0, 2) AS 實際異常率百分比
FROM defects
GROUP BY 規則判定結果;""",
        "note": "💡 【分析思維 Step 4】把前 3 步找到的 4 個分界線組合起來驗證：\n規則：`MaintenanceHours > 10 OR DefectRate > 3.0 OR QualityScore < 75 OR ProductionVolume > 800`\n整體準確率 = `(2710 + 404) / 3240 = 96.11%`！",
        "chart_config": {
            "type": "grouped_bar",
            "x_col": "規則判定結果",
            "y1_col": "實際異常_1",
            "y2_col": "實際正常_0"
        }
    },
    {
        "id": "adv1_risk_scorecard",
        "lang": "sql",
        "title": "【SQL 進階 1】風險燈號計分卡：觸發 1 個紅燈 vs 4 個紅燈有差嗎？",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """WITH risk_calc AS (
    SELECT 
        DefectStatus,
        (CASE WHEN MaintenanceHours > 10 THEN 1 ELSE 0 END +
         CASE WHEN DefectRate > 3.0 THEN 1 ELSE 0 END +
         CASE WHEN QualityScore < 75.0 THEN 1 ELSE 0 END +
         CASE WHEN ProductionVolume > 800 THEN 1 ELSE 0 END) AS 觸發紅燈數
    FROM defects
)
SELECT 
    觸發紅燈數 || ' 個紅燈' AS 風險等級,
    COUNT(*) AS 總筆數,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM defects), 1) AS 佔總樣本比例,
    SUM(DefectStatus) AS 實際異常數,
    ROUND(AVG(DefectStatus) * 100.0, 2) AS 異常率百分比
FROM risk_calc
GROUP BY 觸發紅燈數
ORDER BY 觸發紅燈數;""",
        "note": "💡 【進階 SQL 技巧：CTE (WITH 語法) + 風險計分卡】\n1. **0 個紅燈**：異常率僅 **3.12%**（非常安全）。\n2. **1~4 個紅燈**：異常率皆為 **96%** 左右！證明產線是「一票否決制（木桶短板效應）」。",
        "chart_config": {
            "type": "bar_line",
            "x_col": "風險等級",
            "y1_col": "異常率百分比",
            "y2_col": "總筆數"
        }
    },
    {
        "id": "adv2_root_cause_attribution",
        "lang": "sql",
        "title": "【SQL 進階 2】抓出頭號戰犯：哪一個條件「單獨害死」最多批次？",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """WITH flags AS (
    SELECT 
        DefectStatus,
        (CASE WHEN MaintenanceHours > 10 THEN 1 ELSE 0 END) AS f_maint,
        (CASE WHEN DefectRate > 3.0 THEN 1 ELSE 0 END) AS f_defect,
        (CASE WHEN QualityScore < 75.0 THEN 1 ELSE 0 END) AS f_qual,
        (CASE WHEN ProductionVolume > 800 THEN 1 ELSE 0 END) AS f_vol
    FROM defects
)
SELECT 
    CASE 
        WHEN f_maint=1 AND f_defect=0 AND f_qual=0 AND f_vol=0 THEN '1) 僅【維護時數>10】單獨觸發'
        WHEN f_maint=0 AND f_defect=1 AND f_qual=0 AND f_vol=0 THEN '2) 僅【缺陷率>3.0】單獨觸發'
        WHEN f_maint=0 AND f_defect=0 AND f_qual=1 AND f_vol=0 THEN '3) 僅【品質分數<75】單獨觸發'
        WHEN f_maint=0 AND f_defect=0 AND f_qual=0 AND f_vol=1 THEN '4) 僅【生產量>800】單獨觸發'
        WHEN (f_maint+f_defect+f_qual+f_vol) >= 2 THEN '5) 複合型 (同時2項以上失守)'
        ELSE '0) 四項全數正常 (安全區)'
    END AS 異常根因歸因,
    COUNT(*) AS 發生筆數,
    SUM(DefectStatus) AS 導致缺陷筆數,
    ROUND(SUM(DefectStatus) * 100.0 / (SELECT SUM(DefectStatus) FROM defects), 1) AS 佔全廠缺陷總數比例,
    ROUND(AVG(DefectStatus) * 100.0, 1) AS 該情境異常率
FROM flags
GROUP BY 異常根因歸因
ORDER BY 異常根因歸因;""",
        "note": "💡 【進階業務分析：獨立根因歸因 (Root Cause Attribution)】\n優先改善「維護時數過長 (>10h)」，單一措施就能直接消除全廠 17.3% (472筆) 的異常批次！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "異常根因歸因",
            "y1_col": "佔全廠缺陷總數比例",
            "y2_col": "發生筆數"
        }
    },
    {
        "id": "adv3_crosstab_pivot",
        "lang": "sql",
        "title": "【SQL 進階 3】雙維度交叉表 (Pivot)：維護時數 × 其他條件的交互驗證",
        "step_tag": "自訂探索筆記",
        "sql": """SELECT 
    CASE WHEN MaintenanceHours > 10 THEN '高維護時數 (>10h)' ELSE '正常維護 (<=10h)' END AS 維護狀態,
    COUNT(*) AS 總樣本數,
    ROUND(AVG(CASE WHEN DefectRate <= 3.0 THEN DefectStatus END) * 100.0, 1) AS 當缺陷率正常時_異常率,
    ROUND(AVG(CASE WHEN DefectRate > 3.0 THEN DefectStatus END) * 100.0, 1) AS 當缺陷率超標時_異常率,
    ROUND(AVG(CASE WHEN DefectRate <= 3.0 AND QualityScore >= 75 AND ProductionVolume <= 800 THEN DefectStatus END) * 100.0, 1) AS 當其餘三項皆正常時_異常率
FROM defects
GROUP BY 維護狀態
ORDER BY 維護狀態 DESC;""",
        "note": "💡 【進階 SQL 技巧：用 AVG(CASE WHEN ...) 做出 Excel 樞紐分析表】\n在 `AVG()` 裡面包 `CASE WHEN`，就能把欄位「橫向展開」做雙維度交叉比對！",
        "chart_config": {
            "type": "grouped_bar",
            "x_col": "維護狀態",
            "y1_col": "當缺陷率正常時_異常率",
            "y2_col": "當其餘三項皆正常時_異常率"
        }
    },
    {
        "id": "adv4_window_function_top_cost",
        "lang": "sql",
        "title": "【SQL 進階 4】視窗函數 (Window Function)：各產量級距單件成本最高前 3 名",
        "step_tag": "自訂探索筆記",
        "sql": """WITH cost_analysis AS (
    SELECT 
        CASE 
            WHEN ProductionVolume <= 300 THEN '1_小批量 (100~300)'
            WHEN ProductionVolume <= 700 THEN '2_中批量 (301~700)'
            ELSE '3_大批量 (701~999)'
        END AS 產量級距,
        ProductionVolume AS 生產量,
        ROUND(ProductionCost, 0) AS 總生產成本,
        ROUND(ProductionCost / ProductionVolume, 2) AS 單件成本,
        ROUND(QualityScore, 1) AS 品質分數,
        MaintenanceHours AS 維護時數,
        DefectStatus,
        ROW_NUMBER() OVER (
            PARTITION BY CASE 
                WHEN ProductionVolume <= 300 THEN '1_小批量 (100~300)'
                WHEN ProductionVolume <= 700 THEN '2_中批量 (301~700)'
                ELSE '3_大批量 (701~999)'
            END 
            ORDER BY (ProductionCost / ProductionVolume) DESC
        ) AS 級距內單件成本排名
    FROM defects
    WHERE DefectStatus = 1
)
SELECT * 
FROM cost_analysis
WHERE 級距內單件成本排名 <= 3
ORDER BY 產量級距, 級距內單件成本排名;""",
        "note": "💡 【進階 SQL 必學語法：ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)】\n分組取前 N 名的標準寫法：先在 CTE 內用 `ROW_NUMBER() OVER(...)` 發號碼牌，再於外層篩選 `排名 <= 3`。",
        "chart_config": {
            "type": "bar",
            "x_col": "產量級距",
            "y1_col": "單件成本",
            "y2_col": ""
        }
    },
    {
        "id": "py1_basic_health_check",
        "lang": "python",
        "title": "【Python 基礎 1】數據體檢三連發 (isnull / duplicated / describe)",
        "step_tag": "Step 1: 看目標 (Target)",
        "sql": """# 系統已自動將目前資料表載入為變數 df (pandas DataFrame)
print("=== 1. 資料表維度 (筆數, 欄位數) ===")
print(df.shape)

print("\\n=== 2. 檢查每個欄位的空值數量 ===")
print(df.isnull().sum())

print("\\n=== 3. 檢查完全重複的紀錄筆數 ===")
print("重複筆數:", df.duplicated().sum())

print("\\n=== 4. 目標變數 DefectStatus 比例 ===")
print(df['DefectStatus'].value_counts(normalize=True).round(4) * 100)

# 最後一行若放一個 DataFrame，會自動顯示在右下方資料表！
df.describe().T[['count', 'mean', 'std', 'min', '50%', 'max']].round(2)""",
        "note": "💡 【Python 探索第一步】\n在 Python 模式中，系統已經自動幫您準備好 `df` (目前的資料表)、`pd`、`np`、`plt`、`sns`。\n程式碼最後一行如果放一個 DataFrame，系統會自動把它轉成右下方的互動式表格！",
        "chart_config": {}
    },
    {
        "id": "py2_seaborn_boxplots",
        "lang": "python",
        "title": "【Python 視覺化 1】用 Seaborn 畫出 4 大關鍵特徵的「分組箱型圖 (Boxplot)」",
        "step_tag": "Step 3: 找分界線 (Threshold)",
        "sql": """# 使用 Matplotlib + Seaborn 一次畫出 4 個關鍵特徵的好壞品分佈對比與分界線
fig, axes = plt.subplots(2, 2, figsize=(11, 7), dpi=130)

features = [
    ('MaintenanceHours', '維護時數 (分界線 > 10)', 10),
    ('DefectRate', '製程缺陷率 (分界線 > 3.0)', 3.0),
    ('QualityScore', '品質評分 (分界線 < 75)', 75.0),
    ('ProductionVolume', '生產量 (分界線 > 800)', 800)
]

for ax, (col, title, threshold) in zip(axes.flat, features):
    sns.boxplot(data=df, x='DefectStatus', y=col, ax=ax, palette=['#38bdf8', '#f43f5e'], width=0.45)
    ax.axhline(threshold, color='#1e293b', linestyle='--', linewidth=2, label=f'黃金分界線 ({threshold})')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xticklabels(['0 (正常)', '1 (異常)'])
    ax.legend(loc='upper right', fontsize=9)

plt.tight_layout()
print("✅ 已成功繪製 4 大關鍵特徵箱型圖！請看下方圖片。")""",
        "note": "💡 【Python 視覺化強項：箱型圖 (Boxplot) + 輔助線】\n`seaborn.boxplot` 可以直接看到整個分佈的中位數、四分位距 (IQR)，加上 `ax.axhline()` 畫出黑色虛線分界線，一眼就能看出 `0 (正常)` 的箱子幾乎完全不會越過黑色虛線！",
        "chart_config": {}
    },
    {
        "id": "py3_correlation_heatmap",
        "lang": "python",
        "title": "【Python 視覺化 2】繪製重點特徵相關係數熱力圖 (sns.heatmap)",
        "step_tag": "Step 2: 篩選重點 (Filter)",
        "sql": """# 挑選與 DefectStatus 最相關的前 8 個欄位畫出相關係數矩陣熱力圖
top_cols = ['DefectStatus', 'MaintenanceHours', 'DefectRate', 'QualityScore', 
            'ProductionVolume', 'StockoutRate', 'SupplierQuality', 'EnergyEfficiency']

corr_matrix = df[top_cols].corr()

plt.figure(figsize=(8.5, 6.5), dpi=130)
sns.heatmap(
    corr_matrix, 
    annot=True,          # 顯示數值
    fmt=".2f",           # 小數點後兩位
    cmap="coolwarm",     # 冷暖色系 (紅正相關、藍負相關)
    vmin=-0.35, vmax=0.35,
    linewidths=1
)
plt.title("重點特徵與 DefectStatus 相關係數熱力圖 (Heatmap)", fontsize=13, fontweight="bold", pad=12)
plt.tight_layout()

# 同時在右下角表格輸出完整相關係數排行
df.corr()[['DefectStatus']].sort_values(by='DefectStatus', key=abs, ascending=False).round(4)""",
        "note": "💡 【Python 熱力圖 (`sns.heatmap`)】\n除了看各欄位對 `DefectStatus` 的相關性之外，熱力圖還能檢查特徵與特徵之間有沒有彼此高度相關（共線性）。",
        "chart_config": {}
    },
    {
        "id": "py4_sklearn_decision_tree",
        "lang": "python",
        "title": "【Python 機器學習 1】10 行程式碼跑「隨機森林 & 剪枝決策樹」抓出特徵重要性",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, export_text

# 僅選取數值型欄位進入模型，避免文字分組欄位 (如 'Low', 'Medium') 造成報錯
X = df.drop(columns=['DefectStatus'], errors='ignore').select_dtypes(include=[np.number])
y = df['DefectStatus']

# 1. 訓練決策樹 (加上 ccp_alpha=0.005 自動剪去無意義雜訊分枝，只留核心規則！)
dt = DecisionTreeClassifier(max_depth=4, ccp_alpha=0.005, random_state=42)
dt.fit(X, y)
print(f"🎯 剪枝後決策樹準確率: {dt.score(X, y)*100:.2f}%\\n")
print("=== 機器學習自動找出的 4 關卡黃金規則 ===")
print(export_text(dt, feature_names=list(X.columns)))

# 2. 訓練隨機森林並畫出特徵重要性排行圖
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X, y)
imp_df = pd.DataFrame({
    '特徵名稱': X.columns,
    '重要性佔比(%)': (rf.feature_importances_ * 100).round(2)
}).sort_values('重要性佔比(%)', ascending=True)

plt.figure(figsize=(8, 5), dpi=130)
colors = ['#e11d48' if v > 5 else '#94a3b8' for v in imp_df['重要性佔比(%)']]
plt.barh(imp_df['特徵名稱'], imp_df['重要性佔比(%)'], color=colors, edgecolor='black')
plt.xlabel('隨機森林特徵重要性 (%)')
plt.title('機器學習模型眼中的關鍵特徵排行 (Random Forest)', fontweight='bold')
plt.grid(axis='x', linestyle='--', alpha=0.5)
plt.tight_layout()

imp_df.sort_values('重要性佔比(%)', ascending=False)""",
        "note": "💡 【當 SQL 探索遇上 Python 機器學習】\n加上 `ccp_alpha=0.005`（剪枝參數）後，決策樹會自動砍掉多餘的枝節，只留下最核心的 4 道關卡，準確率高達 96.14%！",
        "chart_config": {}
    },
    {
        "id": "py5_visual_decision_tree",
        "lang": "python",
        "title": "【Python 機器學習 2】畫出「彩色決策樹闖關流程圖 (plot_tree)」",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """from sklearn.tree import DecisionTreeClassifier, plot_tree

# 僅選取數值型欄位進入模型，避免文字分組欄位造成報錯
X = df.drop(columns=['DefectStatus'], errors='ignore').select_dtypes(include=[np.number])
y = df['DefectStatus']

# 使用 ccp_alpha=0.005 剪枝，讓決策樹只保留最精華的 4 道關卡 (共 5 個最終結果方塊)
dt = DecisionTreeClassifier(max_depth=4, ccp_alpha=0.005, random_state=42)
dt.fit(X, y)

plt.figure(figsize=(14, 8), dpi=150)
plot_tree(
    dt,
    feature_names=list(X.columns),
    class_names=['0 (正常良品)', '1 (異常缺陷)'],
    filled=True,       # 依類別自動填色：藍色=偏異常(1)，橘色=偏正常(0)
    rounded=True,      # 圓角方塊
    impurity=False,    # 隱藏 gini 數值讓畫面更乾淨
    fontsize=10
)
plt.title("製造業缺陷判定 - 決策樹 4 關卡彩色流程圖 (往左箭頭 = Yes 符合條件，往右箭頭 = No 不符合)", fontsize=13, fontweight="bold", pad=12)
plt.tight_layout()

print("💡 【彩色決策樹讀圖指南】（點上方圖片可放大檢視）：")
print("1. 每個方塊的第一行是『闖關條件』：往左走代表 Yes (True)，往右走代表 No (False)。")
print("2. samples = 走到這一關的總筆數。")
print("3. value = [正常品數量, 異常品數量]。")
print("4. class = 最終判定結果（全圖只有最底下橘色那塊 417 筆是『0 正常良品』，其餘 4 塊深藍色全是『1 異常缺陷』！）")

# 在右下角表格整理出這 5 個終點方塊 (葉節點) 的白話文規則對照表
pd.DataFrame([
    {"關卡路徑": "第1關淘汰", "條件規則": "MaintenanceHours > 10.5", "總筆數(samples)": 1782, "正常數": 77, "異常數": 1705, "最終判定": "1 (異常 95.7%)"},
    {"關卡路徑": "第2關淘汰", "條件規則": "維護<=10.5 但 DefectRate > 2.99", "總筆數(samples)": 651, "正常數": 17, "異常數": 634, "最終判定": "1 (異常 97.4%)"},
    {"關卡路徑": "第3關淘汰", "條件規則": "前兩關過 但 QualityScore <= 74.88", "總筆數(samples)": 274, "正常數": 12, "異常數": 262, "最終判定": "1 (異常 95.6%)"},
    {"關卡路徑": "第4關淘汰", "條件規則": "前三關過 但 ProductionVolume > 801", "總筆數(samples)": 116, "正常數": 3, "異常數": 113, "最終判定": "1 (異常 97.4%)"},
    {"關卡路徑": "🎉 四關全過", "條件規則": "維護<=10.5 且 缺陷<=2.99 且 品質>74.88 且 產量<=801", "總筆數(samples)": 417, "正常數": 404, "異常數": 13, "最終判定": "0 (正常 96.9%)"}
])""",
        "note": "💡 【怎麼看這張彩色決策樹流程圖？】\n1. **看顏色**：方塊越藍代表「1 (異常)」比例越高；方塊呈現橘色代表「0 (正常良品)」比例越高。\n2. **看方向**：每個方塊往下分岔時，**左邊箭頭永遠代表 `True (符合條件)`**，**右邊箭頭永遠代表 `False (不符合條件)`**。\n3. **看右下角表格**：我已經把圖上 5 個終點方塊的數字整理成右下角的中文表格，對照著看 10 秒就完全懂了！\n*(小技巧：點擊左下方的流程圖圖片，可以在新分頁打開高清大圖！)*",
        "chart_config": {}
    },
    {
        "id": "sql_join_machines_suppliers",
        "lang": "sql",
        "title": "【多表 JOIN 實戰】串聯「機台主檔(machines)」與「供應商主檔(suppliers)」分析各廠區異常率",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """-- 🔗 透過 MachineID 與 SupplierID 同時串聯三張表：defects + machines + suppliers
SELECT 
    m.PlantArea AS 所屬廠區,
    m.MachineID AS 機台編號,
    m.MachineName AS 機台名稱,
    m.InstallYear AS 啟用年份,
    COUNT(*) AS 工單總筆數,
    ROUND(AVG(d.MaintenanceHours), 1) AS 平均維護時數,
    ROUND(AVG(d.DefectStatus) * 100.0, 2) AS 異常率百分比
FROM defects AS d
LEFT JOIN machines AS m 
    ON d.MachineID = m.MachineID
LEFT JOIN suppliers AS s 
    ON d.SupplierID = s.SupplierID
GROUP BY m.PlantArea, m.MachineID, m.MachineName, m.InstallYear
ORDER BY 異常率百分比 DESC;""",
        "note": "💡 【多表關聯 SQL JOIN 實戰教學】\n1. 我們把工單主表 `defects` 透過 `MachineID` 關聯到 `machines`（機台主檔），再透過 `SupplierID` 關聯到 `suppliers`（供應商主檔）。\n2. 一關聯起來真相大白：**「一廠-重載成型區 (MC-106 ~ MC-108)」** 都是 2016~2018 年啟用的老舊機台，平均每週維護時數高達 16~17 小時，導致異常率高達 **95% 以上**！\n3. 相反地，**「三廠-全自動新世代區 (MC-101 ~ MC-102)」** 是 2023~2024 年的新機台，平均維護僅 2.5 小時，異常率大幅降低！",
        "chart_config": {
            "type": "bar_line",
            "x_col": "機台名稱",
            "y1_col": "異常率百分比",
            "y2_col": "平均維護時數"
        }
    },
    {
        "id": "py_merge_machines_suppliers",
        "lang": "python",
        "title": "【Python 多表合併】用 pd.merge 結合三張表分析「供應商等級 x 廠區」表現",
        "step_tag": "Step 4: 規則驗證 (Validate)",
        "sql": """# 🐍 使用 tables['表名'] 調用另外兩張主檔表，並用 pd.merge 左右關聯
df_orders = tables['defects']
df_sup = tables['suppliers']
df_mac = tables['machines']

# 1. 先串聯供應商主檔 (依 SupplierID)
merged = pd.merge(df_orders, df_sup, on='SupplierID', how='left')

# 2. 再串聯機台主檔 (依 MachineID)
merged = pd.merge(merged, df_mac, on='MachineID', how='left')

print(f"✅ 三表合併完成！總筆數: {len(merged)} 筆，欄位數由 {df_orders.shape[1]} 欄擴充為 {merged.shape[1]} 欄")

# 3. 繪製「各廠區 x 供應商合約等級」的平均不良率熱力比較圖
plt.figure(figsize=(8, 4.5), dpi=130)
pivot_tbl = merged.pivot_table(index='PlantArea', columns='ContractTier', values='DefectStatus', aggfunc=lambda x: round(x.mean()*100, 1))
sns.heatmap(pivot_tbl, annot=True, fmt='.1f', cmap='YlOrRd', cbar_kws={'label': '異常率 (%)'})
plt.title('跨表分析：不同廠區 (PlantArea) × 供應商等級 (ContractTier) 異常率 (%)', fontweight='bold', pad=12)
plt.tight_layout()

# 4. 在右下角表格輸出依「供應商名稱」統計的來料品質與交期表現
summary = (
    merged.groupby(['SupplierID', 'SupplierName', 'ContractTier', 'MaterialCategory'], as_index=False)
    .agg(
        工單筆數=('OrderID', 'count'),
        平均來料品質=('SupplierQuality', lambda x: round(x.mean(), 2)),
        平均交貨延遲=('DeliveryDelay', lambda x: round(x.mean(), 2)),
        異常率百分比=('DefectStatus', lambda x: round(x.mean() * 100, 2))
    )
    .sort_values('平均來料品質', ascending=False)
)
summary""",
        "note": "💡 【Python `pd.merge` 跨表分析重點】\n1. 在 Python 模式中，直接用 `tables['suppliers']` 與 `tables['machines']` 就能拿到另外兩張表的 DataFrame。\n2. 用 `pd.merge(左表, 右表, on='共同欄位', how='left')` 就能把供應商名稱、合約等級、所屬廠區全部合併進來，接著就能畫出跨表交叉熱力圖 (`pivot_table` + `sns.heatmap`)！",
        "chart_config": {}
    }
]


def generate_starter_notes_for_table(df, table_name, target_col=None):
    """
    針對任何新匯入的資料表，自動偵測欄位型態與相關係數，
    動態生成專屬該資料表的 7 條 SQL + Python 實戰分析筆記！
    """
    if table_name == "defects" and (not target_col or target_col == "DefectStatus"):
        return DEFECTS_DEFAULT_QUERIES

    cols = list(df.columns)
    if not cols:
        return []

    if not target_col or target_col not in cols:
        target_col = cols[-1]

    num_cols = list(df.select_dtypes(include=[np.number]).columns)
    feature_num_cols = [c for c in num_cols if c != target_col]

    # 計算與 target_col 最相關的前幾個數值欄位
    top_features = feature_num_cols[:4]
    if target_col in num_cols and len(feature_num_cols) > 0 and df[target_col].nunique() > 1:
        try:
            corr_s = df[num_cols].corr()[target_col].drop(target_col, errors="ignore").dropna()
            top_features = list(corr_s.abs().sort_values(ascending=False).index[:4])
        except Exception:
            pass

    f1 = top_features[0] if len(top_features) > 0 else cols[0]
    f2 = top_features[1] if len(top_features) > 1 else f1

    # 判斷 target_col 是否為 0/1 二元變數
    unique_vals = set(df[target_col].dropna().unique())
    is_binary_01 = unique_vals.issubset({0, 1, 0.0, 1.0}) and len(unique_vals) == 2
    target_metric_sql = (
        f'ROUND(AVG("{target_col}") * 100.0, 2) AS "{target_col}_比率百分比"'
        if is_binary_01
        else f'ROUND(AVG("{target_col}"), 2) AS "{target_col}_平均值"'
    )
    target_metric_col = f"{target_col}_比率百分比" if is_binary_01 else f"{target_col}_平均值"

    # Step 2 平均對比 SQL 欄位列表
    avg_exprs = [f'    ROUND(AVG("{c}"), 2) AS "平均_{c}"' for c in top_features[:5]]
    avg_sql_block = ",\n".join(avg_exprs) if avg_exprs else "    COUNT(*) AS 樣本數"

    # Step 3 針對 f1 的自動分區間 SQL
    if f1 in num_cols and df[f1].nunique() > 20:
        span1 = float(df[f1].max() - df[f1].min())
        step1 = round(span1 / 8) if span1 > 50 else round(span1 / 8, 2) or 1
        step3_f1_sql = f"""-- 針對關鍵欄位 {f1} 自動切區間，觀察對 {target_col} 的影響
SELECT 
    CAST(ROUND("{f1}" / {step1}) * {step1} AS TEXT) AS "{f1}_區間",
    COUNT(*) AS 總筆數,
    {target_metric_sql}
FROM "{table_name}"
GROUP BY ROUND("{f1}" / {step1}) * {step1}
ORDER BY ROUND("{f1}" / {step1}) * {step1};"""
        f1_x_col = f"{f1}_區間"
    else:
        step3_f1_sql = f"""-- 觀察不同 {f1} 下的筆數與 {target_col} 變化
SELECT 
    "{f1}",
    COUNT(*) AS 總筆數,
    {target_metric_sql}
FROM "{table_name}"
GROUP BY "{f1}"
ORDER BY "{f1}";"""
        f1_x_col = f1

    # Step 3 針對 f2 的自動分區間 SQL
    if f2 in num_cols and df[f2].nunique() > 20:
        span2 = float(df[f2].max() - df[f2].min())
        step2_val = round(span2 / 8) if span2 > 50 else round(span2 / 8, 2) or 1
        step3_f2_sql = f"""-- 針對第二關鍵欄位 {f2} 自動切區間，觀察對 {target_col} 的影響
SELECT 
    CAST(ROUND("{f2}" / {step2_val}) * {step2_val} AS TEXT) AS "{f2}_區間",
    COUNT(*) AS 總筆數,
    {target_metric_sql}
FROM "{table_name}"
GROUP BY ROUND("{f2}" / {step2_val}) * {step2_val}
ORDER BY ROUND("{f2}" / {step2_val}) * {step2_val};"""
        f2_x_col = f"{f2}_區間"
    else:
        step3_f2_sql = f"""-- 觀察不同 {f2} 下的筆數與 {target_col} 變化
SELECT 
    "{f2}",
    COUNT(*) AS 總筆數,
    {target_metric_sql}
FROM "{table_name}"
GROUP BY "{f2}"
ORDER BY "{f2}";"""
        f2_x_col = f2

    top_features_repr = repr(top_features[:4])

    notes = [
        {
            "id": f"{table_name}_sql_step1",
            "lang": "sql",
            "title": f"【Step 1 看主角】檢查 {target_col} 的分佈與比例",
            "step_tag": "Step 1: 看目標 (Target)",
            "sql": f"""-- [自動為 {table_name} 生成] 檢查主角欄位 {target_col} 的各類別筆數與佔比
SELECT 
    "{target_col}",
    COUNT(*) AS 筆數,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM "{table_name}"), 2) AS 佔比百分比
FROM "{table_name}"
GROUP BY "{target_col}"
ORDER BY 筆數 DESC
LIMIT 30;""",
            "note": f"💡 【專案 `{table_name}` - Step 1】\n系統已自動將目標欄位設為 `{target_col}`。先觀察各類別筆數與佔比是否平衡！",
            "chart_config": {
                "type": "bar",
                "x_col": target_col,
                "y1_col": "筆數",
                "y2_col": "佔比百分比"
            }
        },
        {
            "id": f"{table_name}_sql_step2",
            "lang": "sql",
            "title": f"【Step 2 全表比較】依 {target_col} 分組比較關鍵指標平均值",
            "step_tag": "Step 2: 篩選重點 (Filter)",
            "sql": f"""-- [自動為 {table_name} 生成] 比較不同 {target_col} 分組下的關鍵數值指標平均差異
SELECT 
    "{target_col}",
    COUNT(*) AS 樣本數,
{avg_sql_block}
FROM "{table_name}"
GROUP BY "{target_col}"
ORDER BY "{target_col}"
LIMIT 20;""",
            "note": f"💡 【專案 `{table_name}` - Step 2】\n系統已自動挑選出與 `{target_col}` 最相關的前幾個數值欄位：{', '.join(top_features[:4])}，比較它們在不同分組下的平均值差異。",
            "chart_config": {
                "type": "grouped_bar",
                "x_col": target_col,
                "y1_col": f"平均_{f1}" if top_features else "樣本數",
                "y2_col": f"平均_{f2}" if len(top_features) > 1 else ""
            }
        },
        {
            "id": f"{table_name}_sql_step3_f1",
            "lang": "sql",
            "title": f"【Step 3 找分界線 A】頭號關鍵欄位 {f1} 對 {target_col} 的影響",
            "step_tag": "Step 3: 找分界線 (Threshold)",
            "sql": step3_f1_sql,
            "note": f"💡 【專案 `{table_name}` - Step 3-A】\n`{f1}` 是目前與 `{target_col}` 相關度排名第 1 的特徵。請觀察左下方雙軸圖中紅色折線（{target_metric_col}）隨 `{f1}` 變化的轉折點！",
            "chart_config": {
                "type": "bar_line",
                "x_col": f1_x_col,
                "y1_col": target_metric_col,
                "y2_col": "總筆數"
            }
        },
        {
            "id": f"{table_name}_sql_step3_f2",
            "lang": "sql",
            "title": f"【Step 3 找分界線 B】第二關鍵欄位 {f2} 對 {target_col} 的影響",
            "step_tag": "Step 3: 找分界線 (Threshold)",
            "sql": step3_f2_sql,
            "note": f"💡 【專案 `{table_name}` - Step 3-B】\n觀察排名第 2 的特徵 `{f2}` 在各區間下對 `{target_col}` 的影響趨勢。",
            "chart_config": {
                "type": "bar_line",
                "x_col": f2_x_col,
                "y1_col": target_metric_col,
                "y2_col": "總筆數"
            }
        },
        {
            "id": f"{table_name}_py_step1_check",
            "lang": "python",
            "title": f"【Python 基礎 1】{table_name} 數據體檢三連發 (空值 / 重複 / describe)",
            "step_tag": "Step 1: 看目標 (Target)",
            "sql": f"""# [自動為 {table_name} 生成] 系統已將 "{table_name}" 載入為 df
print("=== 1. 資料表維度 (筆數, 欄位數) ===")
print(df.shape)

print("\\n=== 2. 檢查每個欄位的空值數量 ===")
print(df.isnull().sum())

print("\\n=== 3. 檢查完全重複的紀錄筆數 ===")
print("重複筆數:", df.duplicated().sum())

print("\\n=== 4. 目標欄位 {target_col} 分佈前 10 項 ===")
print(df['{target_col}'].value_counts(dropna=False).head(10))

# 最後一行自動轉成右下角互動式統計表
df.describe().T.round(2)""",
            "note": f"💡 【Python 自動體檢】\n一鍵檢查 `{table_name}` 的維度、缺失值、重複筆數與統計摘要！",
            "chart_config": {}
        },
        {
            "id": f"{table_name}_py_step2_heatmap",
            "lang": "python",
            "title": f"【Python 視覺化 1】{table_name} 數值欄位相關性熱力圖 (Heatmap)",
            "step_tag": "Step 2: 篩選重點 (Filter)",
            "sql": f"""# [自動為 {table_name} 生成] 計算數值欄位相關係數並繪製熱力圖
num_df = df.select_dtypes(include=[np.number])

if num_df.shape[1] >= 2:
    # 若數值欄位超過 10 個，挑選與目標最相關的前 10 個繪圖以免擁擠
    cols_to_plot = list(num_df.columns[:10])
    if '{target_col}' in num_df.columns:
        corr_target = num_df.corr()['{target_col}'].abs().sort_values(ascending=False)
        cols_to_plot = list(corr_target.index[:10])

    plt.figure(figsize=(8.5, 6.5), dpi=130)
    sns.heatmap(num_df[cols_to_plot].corr(), annot=True, fmt=".2f", cmap="coolwarm", linewidths=1)
    plt.title("{table_name} - 重點數值特徵相關係數熱力圖", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()
    print("✅ 已完成相關性熱力圖繪製！")
else:
    print("⚠️ 數值型欄位不足 2 個，無法繪製相關性熱力圖。")

num_df.corr().round(3) if num_df.shape[1] >= 2 else df.head(20)""",
            "note": f"💡 【Python 相關性矩陣】\n自動挑選出 `{table_name}` 中與 `{target_col}` 最相關的數值特徵繪製熱力圖。",
            "chart_config": {}
        },
        {
            "id": f"{table_name}_py_step3_visual",
            "lang": "python",
            "title": f"【Python 視覺化 2】關鍵特徵 ({', '.join(top_features[:4])}) 分佈與對比圖",
            "step_tag": "Step 3: 找分界線 (Threshold)",
            "sql": f"""# [自動為 {table_name} 生成] 針對前 4 大關鍵數值特徵繪製分組箱型圖或分佈圖
key_cols = [c for c in {top_features_repr} if c in df.columns]
target = '{target_col}'

if len(key_cols) > 0:
    n = len(key_cols)
    rows = 2 if n > 2 else 1
    cols = 2 if n > 1 else 1
    fig, axes = plt.subplots(rows, cols, figsize=(11, 3.6 * rows), dpi=130)
    axes_list = np.array(axes).reshape(-1) if n > 1 else [axes]

    # 若目標變數類別數 <= 8，畫分組箱型圖；否則畫散佈趨勢圖
    is_cat_target = df[target].nunique() <= 8

    for ax, col in zip(axes_list, key_cols):
        if is_cat_target:
            sns.boxplot(data=df, x=target, y=col, ax=ax, palette="Set2", width=0.45)
            ax.set_title(f"{{col}} (依 {{target}} 分組箱型圖)", fontsize=11, fontweight="bold")
        else:
            sns.scatterplot(data=df.sample(min(len(df), 500), random_state=42), x=col, y=target, ax=ax, alpha=0.6)
            ax.set_title(f"{{col}} vs {{target}} 散佈圖", fontsize=11, fontweight="bold")

    plt.tight_layout()
    print("✅ 已繪製關鍵特徵對比圖！")
df[key_cols + ([target] if target not in key_cols else [])].describe().T.round(2)""",
            "note": f"💡 【Python 自動視覺化】\n系統會自動判斷 `{target_col}` 是分類型（畫分組箱型圖 Boxplot）還是連續數值型（畫散佈圖 Scatterplot）！",
            "chart_config": {}
        },
        {
            "id": f"{table_name}_py_step4_ml",
            "lang": "python",
            "title": f"【Python 機器學習】自動訓練隨機森林找出影響 {target_col} 的特徵重要性排行",
            "step_tag": "Step 4: 規則驗證 (Validate)",
            "sql": f"""# [自動為 {table_name} 生成] 自動判別分類或迴歸任務，用隨機森林找出關鍵特徵
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

target = '{target_col}'
clean_df = df.dropna(subset=[target]).copy()

# 取出數值特徵並填補空值
X = clean_df.drop(columns=[target]).select_dtypes(include=[np.number]).fillna(0)
y = clean_df[target]

if X.shape[1] > 0:
    is_classification = (y.nunique() <= 15) or (y.dtype == 'object')
    if is_classification:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        task_name = "分類模型 (Classification)"
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        task_name = "迴歸模型 (Regression)"

    model.fit(X, y)
    score = model.score(X, y)
    print(f"🎯 模型類型: {{task_name}}")
    print(f"🎯 模型擬合分數 (Accuracy / R2): {{score*100:.2f}}%")

    imp_df = pd.DataFrame({{
        '特徵名稱': X.columns,
        '重要性佔比(%)': (model.feature_importances_ * 100).round(2)
    }}).sort_values('重要性佔比(%)', ascending=True)

    plt.figure(figsize=(8, max(4, len(X.columns)*0.35)), dpi=130)
    colors = ['#e11d48' if v >= 10 else '#64748b' for v in imp_df['重要性佔比(%)']]
    plt.barh(imp_df['特徵名稱'], imp_df['重要性佔比(%)'], color=colors, edgecolor='black')
    plt.xlabel('隨機森林特徵重要性 (%)')
    plt.title(f'影響 {{target}} 的關鍵特徵排行 ({{table_name}})', fontweight='bold')
    plt.grid(axis='x', linestyle='--', alpha=0.5)
    plt.tight_layout()
else:
    imp_df = pd.DataFrame({{'提示': ['無足夠數值特徵可供建模']}})

imp_df.sort_values('重要性佔比(%)', ascending=False) if '重要性佔比(%)' in imp_df.columns else imp_df""",
            "note": f"💡 【通用機器學習特徵掃描】\n這段程式碼會自動判斷 `{target_col}` 是分類問題還是連續數值問題，並用隨機森林排出哪些欄位對 `{target_col}` 最具決定性影響力！",
            "chart_config": {}
        }
    ]
    return notes


def get_project_sys_dir(folder=None):
    """Return `system_data/<folder>/` directory path for a specific project folder."""
    f_name = sanitize_folder_name(folder) if folder else DEFAULT_PROJECT_FOLDER
    p_dir = os.path.join(SYSTEM_DATA_DIR, f_name)
    os.makedirs(p_dir, exist_ok=True)
    return p_dir


def list_all_project_folders():
    """Return sorted list of all project folders found in datasets/ and system_data/."""
    folders = {DEFAULT_PROJECT_FOLDER}
    for root_dir in (DATASETS_DIR, SYSTEM_DATA_DIR):
        if os.path.exists(root_dir):
            for entry in os.listdir(root_dir):
                full_p = os.path.join(root_dir, entry)
                if os.path.isdir(full_p):
                    folders.add(entry)
    return sorted(list(folders))


def resolve_folder_for_table(table_name=None, explicit_folder=None):
    """Find which project folder owns `table_name` if `explicit_folder` is not provided."""
    if explicit_folder and explicit_folder != "__ALL__":
        return sanitize_folder_name(explicit_folder)
    if not table_name:
        return DEFAULT_PROJECT_FOLDER
    for f_name in list_all_project_folders():
        db_file = os.path.join(SYSTEM_DATA_DIR, f_name, "workspace.db")
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                row = cur.fetchone()
                conn.close()
                if row:
                    return f_name
            except Exception:
                pass
    return DEFAULT_PROJECT_FOLDER


def get_db_connection(folder=None):
    """Connect to the per-project SQLite database: `system_data/<folder>/workspace.db`."""
    p_dir = get_project_sys_dir(folder)
    db_file = os.path.join(p_dir, "workspace.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def load_all_notes_dict(folder=None):
    """Load per-project notes dictionary from `system_data/<folder>/saved_queries.json`."""
    f_name = sanitize_folder_name(folder) if folder else DEFAULT_PROJECT_FOLDER
    notes_file = os.path.join(get_project_sys_dir(f_name), "saved_queries.json")
    if os.path.exists(notes_file):
        try:
            with open(notes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                notes_dict = {"defects": data}
                save_all_notes_dict(notes_dict, f_name)
                return notes_dict
            elif isinstance(data, dict):
                return data
        except Exception:
            pass
    default_notes = {"defects": DEFECTS_DEFAULT_QUERIES} if f_name == DEFAULT_PROJECT_FOLDER else {}
    save_all_notes_dict(default_notes, f_name)
    return default_notes


def save_all_notes_dict(notes_dict, folder=None):
    f_name = sanitize_folder_name(folder) if folder else DEFAULT_PROJECT_FOLDER
    notes_file = os.path.join(get_project_sys_dir(f_name), "saved_queries.json")
    with open(notes_file, "w", encoding="utf-8") as f:
        json.dump(notes_dict, f, ensure_ascii=False, indent=2)


def load_all_col_dicts(folder=None):
    """Load per-project column bilingual dictionary from `system_data/<folder>/column_dictionary.json`."""
    f_name = sanitize_folder_name(folder) if folder else DEFAULT_PROJECT_FOLDER
    col_file = os.path.join(get_project_sys_dir(f_name), "column_dictionary.json")
    if os.path.exists(col_file):
        try:
            with open(col_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if f_name == DEFAULT_PROJECT_FOLDER:
                    updated = False
                    for k, v in DEFAULT_DEFECTS_COL_DICT.items():
                        if "defects" not in data:
                            data["defects"] = {}
                        if k not in data["defects"]:
                            data["defects"][k] = v
                            updated = True
                    if "suppliers" not in data:
                        data["suppliers"] = DEFAULT_SUPPLIERS_COL_DICT
                        updated = True
                    if "machines" not in data:
                        data["machines"] = DEFAULT_MACHINES_COL_DICT
                        updated = True
                    if updated:
                        save_all_col_dicts(data, f_name)
                return data
        except Exception:
            pass
    col_dicts = (
        {
            "defects": DEFAULT_DEFECTS_COL_DICT,
            "suppliers": DEFAULT_SUPPLIERS_COL_DICT,
            "machines": DEFAULT_MACHINES_COL_DICT
        }
        if f_name == DEFAULT_PROJECT_FOLDER
        else {}
    )
    save_all_col_dicts(col_dicts, f_name)
    return col_dicts


def save_all_col_dicts(col_dicts, folder=None):
    f_name = sanitize_folder_name(folder) if folder else DEFAULT_PROJECT_FOLDER
    col_file = os.path.join(get_project_sys_dir(f_name), "column_dictionary.json")
    with open(col_file, "w", encoding="utf-8") as f:
        json.dump(col_dicts, f, ensure_ascii=False, indent=2)


def read_local_file_to_df(filepath):
    """Read a local .csv / .xlsx / .xls file from disk with encoding fallback."""
    lower = filepath.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(filepath)
    for enc in ["utf-8", "utf-8-sig", "cp950", "big5", "gbk", "latin1"]:
        try:
            return pd.read_csv(filepath, encoding=enc)
        except Exception:
            continue
    raise ValueError(f"無法解析檔案編碼: {filepath}")


def scan_datasets_folders():
    """
    自動掃描 `datasets/` 底下的所有子資料夾！
    每個子資料夾都會在 `system_data/<專案資料夾>/` 建立完全獨立的：
      - `workspace.db` (獨立 SQLite 資料庫)
      - `saved_queries.json` (獨立分析筆記庫)
      - `column_dictionary.json` (獨立中英欄位字典)
    """
    newly_imported = []
    errors = []

    if os.path.exists(DATASETS_DIR):
        for entry in sorted(os.listdir(DATASETS_DIR)):
            sub_path = os.path.join(DATASETS_DIR, entry)
            if not os.path.isdir(sub_path):
                continue
            if entry == DEFAULT_PROJECT_FOLDER:
                continue

            conn = get_db_connection(entry)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = {row["name"] for row in cursor.fetchall()}

            notes_dict = load_all_notes_dict(entry)
            load_all_col_dicts(entry)
            manifest_path = os.path.join(get_project_sys_dir(entry), "source_fingerprints.json")
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    fingerprints = json.load(f)
                if not isinstance(fingerprints, dict):
                    fingerprints = {}
            except (OSError, ValueError):
                fingerprints = {}

            for fname in sorted(os.listdir(sub_path)):
                if not fname.lower().endswith((".csv", ".xlsx", ".xls")):
                    continue
                fpath = os.path.join(sub_path, fname)
                base = os.path.splitext(fname)[0]
                t_name = sanitize_table_name(base)
                try:
                    digest = hashlib.sha256()
                    with open(fpath, "rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                    fingerprint = digest.hexdigest()
                    # Legacy databases have no manifest. Record their current source without
                    # replacing any user-edited table during the first scan after upgrading.
                    if t_name in existing_tables and fname not in fingerprints:
                        fingerprints[fname] = fingerprint
                        continue
                    if t_name in existing_tables and fingerprints.get(fname) == fingerprint:
                        continue
                    df = read_local_file_to_df(fpath)
                    df.to_sql(t_name, conn, if_exists="replace", index=False)
                    if t_name not in existing_tables and not notes_dict.get(t_name):
                        notes_dict[t_name] = generate_starter_notes_for_table(df, t_name)
                    existing_tables.add(t_name)
                    fingerprints[fname] = fingerprint
                    newly_imported.append((entry, t_name))
                except Exception as e:
                    errors.append(f"{entry}/{fname}: {e}")

            save_all_notes_dict(notes_dict, entry)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(fingerprints, f, ensure_ascii=False, indent=2)
            conn.close()

    if newly_imported:
        for f_imported, _ in newly_imported:
            invalidate_table_meta_cache(f_imported)

    return newly_imported, errors


def ensure_erp_companion_tables(conn):
    """
    建立方案 B 的真實工廠 ERP 多表關聯架構（檔案統一收納於 datasets/01_manufacturing_defects/）：
    1. 在主表 defects 加入 OrderID (工單批號)、SupplierID (供應商代碼)、MachineID (機台編號)
    2. 建立並匯入 supplier_master.csv -> 資料表 `suppliers` (6 家供應商主檔)
    3. 建立並匯入 machine_master.csv -> 資料表 `machines` (8 台產線設備主檔)
    """
    os.makedirs(DEFAULT_PROJECT_DIR, exist_ok=True)
    existing_tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if {"defects", "suppliers", "machines"}.issubset(existing_tables):
        return

    # 1. 建立供應商主檔 (suppliers)
    suppliers_data = [
        {"SupplierID": "SUP-01", "SupplierName": "台積精密材料", "MaterialCategory": "高純度合金基材", "Region": "台灣新竹", "ContractTier": "Tier-1 (核心特優)", "LeadTimeDays": 3},
        {"SupplierID": "SUP-02", "SupplierName": "日系東麗高規", "MaterialCategory": "奈米複合塗層", "Region": "日本大阪", "ContractTier": "Tier-1 (核心特優)", "LeadTimeDays": 5},
        {"SupplierID": "SUP-03", "SupplierName": "德州特種化工", "MaterialCategory": "耐熱工業樹脂", "Region": "美國德州", "ContractTier": "Tier-2 (標準合格)", "LeadTimeDays": 7},
        {"SupplierID": "SUP-04", "SupplierName": "南亞高分子廠", "MaterialCategory": "工業級塑化粒子", "Region": "越南平陽", "ContractTier": "Tier-2 (標準合格)", "LeadTimeDays": 4},
        {"SupplierID": "SUP-05", "SupplierName": "永興標準五金", "MaterialCategory": "一般沖壓線材", "Region": "台灣台中", "ContractTier": "Tier-3 (一般備援)", "LeadTimeDays": 6},
        {"SupplierID": "SUP-06", "SupplierName": "宏達低價原料", "MaterialCategory": "回收再生塑料", "Region": "東南亞外包", "ContractTier": "Tier-3 (一般備援)", "LeadTimeDays": 9},
    ]
    df_suppliers = pd.DataFrame(suppliers_data)
    sup_csv_path = os.path.join(DEFAULT_PROJECT_DIR, "supplier_master.csv")
    if "suppliers" not in existing_tables:
        if not os.path.exists(sup_csv_path):
            df_suppliers.to_csv(sup_csv_path, index=False, encoding="utf-8-sig")
        df_suppliers.to_sql("suppliers", conn, if_exists="fail", index=False)

    # 2. 建立產線機台主檔 (machines)
    machines_data = [
        {"MachineID": "MC-101", "MachineName": "三廠-A1全自動光學產線", "PlantArea": "三廠 (全自動新世代區)", "MachineModel": "NeoTech-2024X", "InstallYear": 2024, "MaxCapacity": 950},
        {"MachineID": "MC-102", "MachineName": "三廠-A2智慧精密產線", "PlantArea": "三廠 (全自動新世代區)", "MachineModel": "NeoTech-2023S", "InstallYear": 2023, "MaxCapacity": 900},
        {"MachineID": "MC-103", "MachineName": "二廠-B1高速積層線", "PlantArea": "二廠 (主力標準產區)", "MachineModel": "ProLine-500", "InstallYear": 2021, "MaxCapacity": 820},
        {"MachineID": "MC-104", "MachineName": "二廠-B2高速積層線", "PlantArea": "二廠 (主力標準產區)", "MachineModel": "ProLine-500", "InstallYear": 2021, "MaxCapacity": 820},
        {"MachineID": "MC-105", "MachineName": "二廠-B3雙軸成型線", "PlantArea": "二廠 (主力標準產區)", "MachineModel": "ProLine-450", "InstallYear": 2020, "MaxCapacity": 780},
        {"MachineID": "MC-106", "MachineName": "一廠-C1重載傳統機", "PlantArea": "一廠 (老舊重載產區)", "MachineModel": "Legacy-MK2", "InstallYear": 2018, "MaxCapacity": 750},
        {"MachineID": "MC-107", "MachineName": "一廠-C2重載傳統機", "PlantArea": "一廠 (老舊重載產區)", "MachineModel": "Legacy-MK2", "InstallYear": 2017, "MaxCapacity": 720},
        {"MachineID": "MC-108", "MachineName": "一廠-C3初代成型機", "PlantArea": "一廠 (老舊重載產區)", "MachineModel": "Legacy-MK1", "InstallYear": 2016, "MaxCapacity": 680},
    ]
    df_machines = pd.DataFrame(machines_data)
    mac_csv_path = os.path.join(DEFAULT_PROJECT_DIR, "machine_master.csv")
    if "machines" not in existing_tables:
        if not os.path.exists(mac_csv_path):
            df_machines.to_csv(mac_csv_path, index=False, encoding="utf-8-sig")
        df_machines.to_sql("machines", conn, if_exists="fail", index=False)

    # 3. 檢查並擴充主表 defects（加入 OrderID, SupplierID, MachineID）
    if "defects" not in existing_tables and os.path.exists(DEFAULT_CSV):
        df_raw = pd.read_csv(DEFAULT_CSV)
        rng = np.random.default_rng(42)

        order_ids = [f"ORD-{i+1:04d}" for i in range(len(df_raw))]

        # 依 SupplierQuality 分數合理分配對應的供應商代碼
        sup_ids = []
        for sq in df_raw["SupplierQuality"]:
            if sq >= 95.0:
                sup_ids.append(rng.choice(["SUP-01", "SUP-02"], p=[0.55, 0.45]))
            elif sq >= 88.0:
                sup_ids.append(rng.choice(["SUP-03", "SUP-04"], p=[0.50, 0.50]))
            else:
                sup_ids.append(rng.choice(["SUP-05", "SUP-06"], p=[0.55, 0.45]))

        # 依 MaintenanceHours 維護時數合理分配對應的廠區與機台編號
        mac_ids = []
        for mh in df_raw["MaintenanceHours"]:
            if mh <= 5:
                mac_ids.append(rng.choice(["MC-101", "MC-102"], p=[0.5, 0.5]))
            elif mh <= 10:
                mac_ids.append(rng.choice(["MC-103", "MC-104", "MC-105"], p=[0.35, 0.35, 0.30]))
            else:
                mac_ids.append(rng.choice(["MC-106", "MC-107", "MC-108"], p=[0.34, 0.33, 0.33]))

        df_enriched = df_raw.copy()
        if "MachineID" not in df_enriched.columns:
            df_enriched.insert(0, "MachineID", mac_ids)
        if "SupplierID" not in df_enriched.columns:
            df_enriched.insert(0, "SupplierID", sup_ids)
        if "OrderID" not in df_enriched.columns:
            df_enriched.insert(0, "OrderID", order_ids)

        df_enriched.to_sql("defects", conn, if_exists="fail", index=False)
        erp_orders_csv = os.path.join(DEFAULT_PROJECT_DIR, "production_orders_erp.csv")
        if not os.path.exists(erp_orders_csv):
            df_enriched.to_csv(erp_orders_csv, index=False, encoding="utf-8-sig")


def init_db_and_notes():
    """Initialize SQLite DB, scan datasets/ folders, and init notes."""
    if os.path.exists(DEFAULT_CSV):
        conn = get_db_connection(DEFAULT_PROJECT_FOLDER)
        ensure_erp_companion_tables(conn)
        try:
            notes_dict = load_all_notes_dict(DEFAULT_PROJECT_FOLDER)
            if not notes_dict:
                notes_dict = {"defects": [], "suppliers": [], "machines": []}
                save_all_notes_dict(notes_dict, DEFAULT_PROJECT_FOLDER)
            load_all_col_dicts(DEFAULT_PROJECT_FOLDER)
        except Exception:
            pass
        finally:
            conn.close()

    scan_datasets_folders()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan_folders", methods=["POST"])
def api_scan_folders():
    """Scan `datasets/` subdirectories for any newly dropped folders/CSV files."""
    newly, errors = scan_datasets_folders()
    if newly:
        summary = ", ".join([f"{folder}/{tbl}" for folder, tbl in newly])
        msg = f"✅ 掃描完成！已自動從 datasets/ 建立獨立專案資料庫並匯入 {len(newly)} 張表：{summary}"
    else:
        msg = "✅ 已掃描 datasets/ 資料夾，未發現需要匯入或更新的資料表。"
    if errors:
        msg += f" ⚠️ {len(errors)} 個檔案處理失敗。"
    return jsonify({
        "message": msg,
        "newly_imported": [{"folder": f, "table": t} for f, t in newly],
        "errors": errors
    })


_MEMORY_META_CACHE = {}


def get_meta_cache_path(folder_name):
    """Return file path for `system_data/<folder>/meta_cache.json`."""
    f_clean = sanitize_folder_name(folder_name)
    return os.path.join(get_project_sys_dir(f_clean), "meta_cache.json")


def invalidate_table_meta_cache(folder_name=None):
    """Invalidate in-memory and disk metadata cache for a specific folder or all folders."""
    global _MEMORY_META_CACHE
    if folder_name:
        f_clean = sanitize_folder_name(folder_name)
        _MEMORY_META_CACHE.pop(f_clean, None)
        c_path = get_meta_cache_path(f_clean)
        if os.path.exists(c_path):
            try:
                os.remove(c_path)
            except Exception:
                pass
    else:
        _MEMORY_META_CACHE.clear()
        for f in list_all_project_folders():
            c_path = get_meta_cache_path(f)
            if os.path.exists(c_path):
                try:
                    os.remove(c_path)
                except Exception:
                    pass


def compute_folder_table_meta(folder_name):
    """Compute column metadata, data types, and summary statistics for all tables in a folder."""
    f_name = sanitize_folder_name(folder_name)
    conn = get_db_connection(f_name)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row["name"] for row in cursor.fetchall()]
    f_col_dicts = load_all_col_dicts(f_name)

    result = {}
    for t in tables:
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{t}"', conn)
            t_dict = f_col_dicts.get(t, {})
            cols_info = []
            for col in df.columns:
                dtype_str = str(df[col].dtype)
                is_num = pd.api.types.is_numeric_dtype(df[col])
                c_meta = t_dict.get(col, {})
                info = {
                    "name": col,
                    "zh": c_meta.get("zh", ""),
                    "purpose": c_meta.get("purpose", ""),
                    "dtype": dtype_str,
                    "is_numeric": bool(is_num),
                    "null_count": int(df[col].isnull().sum()),
                    "unique_count": int(df[col].nunique())
                }
                if is_num and len(df) > 0:
                    info["min"] = round(float(df[col].min()), 3)
                    info["max"] = round(float(df[col].max()), 3)
                    info["mean"] = round(float(df[col].mean()), 3)
                cols_info.append(info)
            result[t] = {
                "folder": f_name,
                "row_count": len(df),
                "col_count": len(df.columns),
                "columns": cols_info,
                "col_dict": t_dict
            }
        except Exception as e:
            result[t] = {"folder": f_name, "error": str(e)}
    conn.close()
    return result


def get_folder_table_meta(folder_name, force_refresh=False):
    """Get table metadata for a folder from memory cache, disk cache, or compute if missing."""
    f_name = sanitize_folder_name(folder_name)
    if not force_refresh and f_name in _MEMORY_META_CACHE:
        return _MEMORY_META_CACHE[f_name]

    cache_path = get_meta_cache_path(f_name)
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as fp:
                cached = json.load(fp)
            if isinstance(cached, dict) and cached:
                _MEMORY_META_CACHE[f_name] = cached
                return cached
        except Exception:
            pass

    meta = compute_folder_table_meta(f_name)
    _MEMORY_META_CACHE[f_name] = meta
    try:
        with open(cache_path, "w", encoding="utf-8") as fp:
            json.dump(meta, fp, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return meta


@app.route("/api/tables", methods=["GET"])
def get_tables():
    """Return all tables across per-project databases (or filtered by folder), plus folder list with instant caching."""
    req_folder = request.args.get("folder", "").strip()
    all_folders = list_all_project_folders()

    # Aggregate metadata across all folders using memory/disk cache (< 2ms total)
    all_meta = {}
    for f_name in all_folders:
        all_meta.update(get_folder_table_meta(f_name))

    if req_folder and req_folder in all_folders:
        result = {t: meta for t, meta in all_meta.items() if meta.get("folder") == req_folder}
    else:
        result = all_meta

    folders_meta = {}
    for f_name in all_folders:
        f_tables = [t for t, meta in all_meta.items() if meta.get("folder") == f_name]
        total_rows = sum(all_meta[t].get("row_count", 0) for t in f_tables)
        try:
            f_notes = load_all_notes_dict(f_name)
            total_notes = sum(len(v) for v in f_notes.values())
        except Exception:
            total_notes = 0
        folders_meta[f_name] = {
            "tables": f_tables,
            "total_rows": total_rows,
            "total_tables": len(f_tables),
            "total_notes": total_notes
        }

    return jsonify({
        "tables": result,
        "folders": all_folders,
        "folders_meta": folders_meta
    })


@app.route("/api/col_dict", methods=["GET", "POST"])
def handle_col_dict():
    """Get or update bilingual column dictionary (zh name & analysis purpose) in the project's own folder."""
    table_name = request.args.get("table", "defects")
    folder_arg = request.args.get("folder", "").strip()

    if request.method == "GET":
        f_name = resolve_folder_for_table(table_name, folder_arg)
        all_col_dicts = load_all_col_dicts(f_name)
        return jsonify({"table": table_name, "folder": f_name, "col_dict": all_col_dicts.get(table_name, {})})

    data = request.get_json() or {}
    table_name = data.get("table", table_name)
    f_name = resolve_folder_for_table(table_name, data.get("folder", folder_arg))
    col_dict = data.get("col_dict", {})
    all_col_dicts = load_all_col_dicts(f_name)
    all_col_dicts[table_name] = col_dict
    save_all_col_dicts(all_col_dicts, f_name)
    invalidate_table_meta_cache(f_name)
    return jsonify({
        "message": f"已儲存至專案 `{f_name}` 的專屬欄位字典 (`{table_name}` 共 {len(col_dict)} 個欄位)！",
        "col_dict": col_dict
    })


@app.route("/api/delete_table", methods=["POST"])
def delete_table():
    """Delete a user-imported table and its notes from its project database."""
    data = request.get_json() or {}
    table_name = data.get("table", "").strip()
    f_name = resolve_folder_for_table(table_name, data.get("folder", ""))
    if not table_name:
        return jsonify({"error": "未指定資料表名稱"}), 400
    if table_name == "defects" and f_name == DEFAULT_PROJECT_FOLDER:
        return jsonify({"error": "預設示範專案 `defects` 不可刪除"}), 400

    conn = get_db_connection(f_name)
    try:
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}";')
        conn.commit()
        conn.close()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    notes_dict = load_all_notes_dict(f_name)
    if table_name in notes_dict:
        del notes_dict[table_name]
        save_all_notes_dict(notes_dict, f_name)

    invalidate_table_meta_cache(f_name)
    return jsonify({"message": f"已從專案 `{f_name}` 刪除資料表 `{table_name}` 及其專屬筆記"})


def read_uploaded_file_to_df(file_storage):
    """Helper to parse an uploaded CSV or Excel file into a pandas DataFrame with encoding auto-detection."""
    fname_lower = file_storage.filename.lower()
    if fname_lower.endswith(".xlsx") or fname_lower.endswith(".xls"):
        return pd.read_excel(file_storage)
    raw_bytes = file_storage.read()
    for enc in ["utf-8", "utf-8-sig", "cp950", "big5", "gbk", "latin1"]:
        try:
            return pd.read_csv(io.BytesIO(raw_bytes), encoding=enc)
        except Exception:
            continue
    raise ValueError(f"無法解析檔案 `{file_storage.filename}` 的編碼")


def sanitize_table_name(raw_name):
    t = "".join(c if c.isalnum() or c == "_" else "_" for c in raw_name.strip()).lower()
    if not t or t[0].isdigit():
        t = "table_" + t
    return t


def sanitize_folder_name(raw_folder):
    cleaned = "".join(c if c.isalnum() or c in ("_", "-") or "\u4e00" <= c <= "\u9fff" else "_" for c in str(raw_folder).strip())
    return cleaned or DEFAULT_PROJECT_FOLDER


def safe_upload_stem(filename):
    """Use only a plain filename when deriving a saved CSV or table name."""
    basename = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    stem, extension = os.path.splitext(basename)
    if not stem or extension.lower() not in (".csv", ".xlsx", ".xls"):
        raise ValueError("僅支援具有效檔名的 CSV 或 Excel 檔案")
    return sanitize_table_name(stem)


@app.route("/api/upload_csv", methods=["POST"])
def upload_csv():
    """
    Import single or multiple CSV/Excel files into the project folder's dedicated SQLite database (`system_data/<project_folder>/workspace.db`)
    and save physical files under `datasets/<project_folder>/`.
    """
    uploaded_files = request.files.getlist("files")
    if not uploaded_files and "file" in request.files:
        uploaded_files = [request.files["file"]]
    uploaded_files = [f for f in uploaded_files if f and f.filename]

    if not uploaded_files:
        return jsonify({"error": "未選擇任何檔案"}), 400

    try:
        upload_stems = [safe_upload_stem(f.filename) for f in uploaded_files]
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    import_mode = request.form.get("import_mode", "separate").strip()
    custom_table_name = request.form.get("table_name", "").strip()
    raw_folder = request.form.get("project_folder", "").strip()
    if not raw_folder:
        base0 = upload_stems[0]
        project_folder = sanitize_folder_name(base0)
    else:
        project_folder = sanitize_folder_name(raw_folder)

    target_folder_dir = os.path.join(DATASETS_DIR, project_folder)
    os.makedirs(target_folder_dir, exist_ok=True)

    try:
        conn = get_db_connection(project_folder)
        notes_dict = load_all_notes_dict(project_folder)
        load_all_col_dicts(project_folder)

        if import_mode == "concat" and len(uploaded_files) >= 1:
            dfs = []
            for f, safe_stem in zip(uploaded_files, upload_stems):
                part_df = read_uploaded_file_to_df(f)
                part_df.to_csv(os.path.join(target_folder_dir, safe_stem + ".csv"), index=False, encoding="utf-8-sig")
                part_df.insert(0, "SourceFile", f.filename)
                dfs.append(part_df)
            merged_df = pd.concat(dfs, ignore_index=True)

            if custom_table_name:
                target_table = sanitize_table_name(custom_table_name)
            else:
                base0 = upload_stems[0]
                target_table = sanitize_table_name(f"{base0}_merged_{len(uploaded_files)}files")

            merged_df.to_sql(target_table, conn, if_exists="replace", index=False)
            merged_df.to_csv(os.path.join(target_folder_dir, f"{target_table}.csv"), index=False, encoding="utf-8-sig")
            conn.close()

            starter_notes = generate_starter_notes_for_table(merged_df, target_table)
            notes_dict[target_table] = starter_notes
            save_all_notes_dict(notes_dict, project_folder)
            invalidate_table_meta_cache(project_folder)

            return jsonify({
                "message": f"已將 {len(uploaded_files)} 個檔案存入 `datasets/{project_folder}/` 與獨立資料庫 `system_data/{project_folder}/workspace.db` (`{target_table}`)！",
                "table_name": target_table,
                "project_folder": project_folder,
                "imported_tables": [target_table]
            })
        else:
            imported_tables = []
            for idx, f in enumerate(uploaded_files):
                df = read_uploaded_file_to_df(f)
                if len(uploaded_files) == 1 and custom_table_name:
                    t_name = sanitize_table_name(custom_table_name)
                else:
                    t_name = upload_stems[idx]

                df.to_sql(t_name, conn, if_exists="replace", index=False)
                df.to_csv(os.path.join(target_folder_dir, f"{t_name}.csv"), index=False, encoding="utf-8-sig")
                starter_notes = generate_starter_notes_for_table(df, t_name)
                notes_dict[t_name] = starter_notes
                imported_tables.append(t_name)

            conn.close()
            save_all_notes_dict(notes_dict, project_folder)
            invalidate_table_meta_cache(project_folder)
            last_table = imported_tables[-1]
            return jsonify({
                "message": f"成功匯入 {len(imported_tables)} 張表至專屬專案 `datasets/{project_folder}/`（獨立資料庫 `system_data/{project_folder}/workspace.db`）！",
                "table_name": last_table,
                "project_folder": project_folder,
                "imported_tables": imported_tables
            })
    except Exception as e:
        return jsonify({"error": f"匯入失敗: {str(e)}"}), 400


@app.route("/api/combine_tables", methods=["POST"])
def combine_tables():
    """
    Combine existing tables inside a project folder's SQLite database either horizontally (JOIN / pd.merge)
    or vertically (UNION ALL / pd.concat) and save the result as a new table in that project's database & datasets folder.
    """
    data = request.get_json() or {}
    mode = data.get("mode", "join")  # 'join' or 'union'
    new_table_raw = (data.get("new_table", "") or data.get("new_table_name", "")).strip()
    req_folder = data.get("folder", "").strip()

    if mode == "join":
        left_table = data.get("left_table", "").strip()
        target_folder = resolve_folder_for_table(left_table, req_folder)
    else:
        tables_list = data.get("tables", [])
        first_t = tables_list[0] if tables_list else ""
        target_folder = resolve_folder_for_table(first_t, req_folder)

    conn = get_db_connection(target_folder)
    try:
        if mode == "join":
            left_table = data.get("left_table", "").strip()
            right_table = data.get("right_table", "").strip()
            left_key = data.get("left_key", "").strip()
            right_key = data.get("right_key", "").strip()
            join_how = data.get("join_how", "left").strip().lower()
            if join_how not in ("left", "inner", "outer"):
                join_how = "left"

            if not left_table or not right_table or not left_key or not right_key:
                conn.close()
                return jsonify({"error": "請選擇左表、右表與對應的關聯欄位 (Key)"}), 400

            df_left = pd.read_sql_query(f'SELECT * FROM "{left_table}"', conn)
            df_right = pd.read_sql_query(f'SELECT * FROM "{right_table}"', conn)

            merged_df = pd.merge(
                df_left,
                df_right,
                left_on=left_key,
                right_on=right_key,
                how=join_how,
                suffixes=("", f"_{right_table}")
            )
            new_table = sanitize_table_name(new_table_raw or f"{left_table}_join_{right_table}")

            all_col_dicts = load_all_col_dicts(target_folder)
            combined_dict = {}
            combined_dict.update(all_col_dicts.get(right_table, {}))
            combined_dict.update(all_col_dicts.get(left_table, {}))
            if combined_dict:
                all_col_dicts[new_table] = combined_dict
                save_all_col_dicts(all_col_dicts, target_folder)
        else:
            tables_list = data.get("tables", [])
            if not tables_list or len(tables_list) < 2:
                conn.close()
                return jsonify({"error": "請至少勾選 2 張要上下合併的資料表"}), 400

            dfs = []
            for t in tables_list:
                part_df = pd.read_sql_query(f'SELECT * FROM "{t}"', conn)
                part_df.insert(0, "SourceTable", t)
                dfs.append(part_df)
            merged_df = pd.concat(dfs, ignore_index=True)
            new_table = sanitize_table_name(new_table_raw or f"union_{len(tables_list)}_tables")

            all_col_dicts = load_all_col_dicts(target_folder)
            combined_dict = {"SourceTable": {"zh": "來源資料表", "purpose": "區分合併前各表來源"}}
            for t in tables_list:
                combined_dict.update(all_col_dicts.get(t, {}))
            all_col_dicts[new_table] = combined_dict
            save_all_col_dicts(all_col_dicts, target_folder)

        merged_df.to_sql(new_table, conn, if_exists="replace", index=False)
        conn.close()

        target_folder_dir = os.path.join(DATASETS_DIR, target_folder)
        os.makedirs(target_folder_dir, exist_ok=True)
        merged_df.to_csv(os.path.join(target_folder_dir, f"{new_table}.csv"), index=False, encoding="utf-8-sig")

        notes_dict = load_all_notes_dict(target_folder)
        starter_notes = generate_starter_notes_for_table(merged_df, new_table)
        notes_dict[new_table] = starter_notes
        save_all_notes_dict(notes_dict, target_folder)
        invalidate_table_meta_cache(target_folder)

        return jsonify({
            "message": f"成功建立合併表 `{new_table}`（已存入 `datasets/{target_folder}/{new_table}.csv` 與專屬資料庫，共 {len(merged_df)} 筆）！",
            "table_name": new_table,
            "project_folder": target_folder
        })
    except Exception as e:
        conn.close()
        return jsonify({"error": f"合併資料表失敗: {str(e)}"}), 400


def to_serializable(val):
    """Convert numpy/pandas types to native JSON-serializable Python types."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return str(val)
    return val


def dataframe_to_response_dict(df):
    """Helper to convert a pandas DataFrame into standard JSON table payload."""
    try:
        if isinstance(df, pd.Series):
            df = df.to_frame()
        df = df.copy()
        if not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()

        # 扁平化 MultiIndex 欄位或非字串欄位 (避免 Pivot Table 欄位為整數年份時報錯)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join([str(p) for p in col if str(p) != ""]).strip() for col in df.columns.values]
        else:
            df.columns = [str(c) for c in df.columns]

        # 將 Categorical 型態轉為一般字串/物件，避免 pd.cut 產生的欄位在轉 JSON 時報錯
        for col in df.columns:
            if isinstance(df[col].dtype, pd.CategoricalDtype):
                df[col] = df[col].astype(object).where(df[col].notnull(), None)

        raw_records = df.where(pd.notnull(df), None).to_dict(orient="records")
        clean_records = []
        for r in raw_records[:2000]:
            clean_records.append({str(k): to_serializable(v) for k, v in r.items()})

        columns = [str(c) for c in df.columns]

        col_stats = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]) and len(df) > 0:
                s = df[col].dropna()
                if len(s) > 0:
                    col_stats[str(col)] = {
                        "min": round(float(s.min()), 4),
                        "max": round(float(s.max()), 4),
                        "mean": round(float(s.mean()), 4),
                        "sum": round(float(s.sum()), 4)
                    }

        return {
            "columns": columns,
            "rows": clean_records,
            "total_rows": len(df),
            "truncated": len(df) > 2000,
            "col_stats": col_stats
        }
    except Exception:
        return None


@app.route("/api/query", methods=["POST"])
def execute_query():
    """Execute SQL query against the selected project folder's SQLite database."""
    data = request.get_json() or {}
    sql = data.get("sql", "").strip()
    table_name = data.get("table", "")
    f_name = resolve_folder_for_table(table_name, data.get("folder", ""))
    if not sql:
        return jsonify({"error": "請輸入 SQL 指令"}), 400

    conn = get_db_connection(f_name)
    try:
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return jsonify(dataframe_to_response_dict(df))
    except Exception as e:
        conn.close()
        return jsonify({"error": f"SQL 執行錯誤：{str(e)}"}), 400


@app.route("/api/run_python", methods=["POST"])
def execute_python():
    """Execute Python analysis code against the selected project folder's SQLite database."""
    data = request.get_json() or {}
    code = data.get("code", "").strip()
    table_name = data.get("table", "defects")
    f_name = resolve_folder_for_table(table_name, data.get("folder", ""))

    if not code:
        return jsonify({"error": "請輸入 Python 程式碼"}), 400

    conn = get_db_connection(f_name)
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
        if "DefectRate" in df.columns and "DefectRatePct" not in df.columns and "DefectRatePct" in code:
            df["DefectRatePct"] = df["DefectRate"]
    except Exception as e:
        conn.close()
        return jsonify({"error": f"讀取資料表失敗: {str(e)}"}), 400

    plt.close("all")
    stdout_buf = io.StringIO()

    class LazyTablesDict(dict):
        def __getitem__(self, key):
            if key not in self:
                super().__setitem__(key, pd.read_sql_query(f'SELECT * FROM "{key}"', conn))
            return super().__getitem__(key)

    tables_helper = LazyTablesDict()
    tables_helper[table_name] = df

    env = {
        "df": df,
        "tables": tables_helper,
        "table_name": table_name,
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "conn": conn
    }
    initial_keys = set(env.keys())

    result_obj = None
    try:
        with contextlib.redirect_stdout(stdout_buf):
            tree = ast.parse(code, mode="exec")
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                last_expr_node = tree.body[-1].value
                is_print_call = (
                    isinstance(last_expr_node, ast.Call)
                    and isinstance(last_expr_node.func, ast.Name)
                    and last_expr_node.func.id == "print"
                )
                if is_print_call:
                    exec(compile(tree, filename="<python_workspace>", mode="exec"), env)
                    if last_expr_node.args and isinstance(last_expr_node.args[0], ast.Name):
                        arg_name = last_expr_node.args[0].id
                        if arg_name in env and isinstance(env[arg_name], (pd.DataFrame, pd.Series)):
                            result_obj = env[arg_name]
                else:
                    last_expr = ast.Expression(tree.body.pop().value)
                    if tree.body:
                        exec(compile(tree, filename="<python_workspace>", mode="exec"), env)
                    result_obj = eval(compile(last_expr, filename="<python_workspace>", mode="eval"), env)
            else:
                exec(compile(tree, filename="<python_workspace>", mode="exec"), env)

            if result_obj is None:
                for preferred_name in ["result", "result_df", "res", "summary", "grouped", "out"]:
                    if preferred_name in env and isinstance(env[preferred_name], (pd.DataFrame, pd.Series)):
                        result_obj = env[preferred_name]
                        break
            if result_obj is None:
                new_dfs = [
                    v for k, v in env.items()
                    if k not in initial_keys and not k.startswith("_") and isinstance(v, (pd.DataFrame, pd.Series))
                ]
                if new_dfs:
                    result_obj = new_dfs[-1]
    except Exception:
        conn.close()
        err_trace = traceback.format_exc()
        return jsonify({
            "error": "Python 執行發生錯誤",
            "stdout": stdout_buf.getvalue(),
            "traceback": err_trace
        }), 400

    conn.close()

    plot_base64 = None
    if plt.get_fignums():
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format="png", bbox_inches="tight", dpi=130)
        img_buf.seek(0)
        plot_base64 = "data:image/png;base64," + base64.b64encode(img_buf.read()).decode("utf-8")
        plt.close("all")

    table_payload = None
    if isinstance(result_obj, (pd.DataFrame, pd.Series)):
        try:
            table_payload = dataframe_to_response_dict(result_obj)
        except Exception:
            table_payload = None
    elif result_obj is not None:
        stdout_buf.write(f"\n[回傳結果]:\n{repr(result_obj)}\n")

    try:
        return jsonify({
            "stdout": stdout_buf.getvalue(),
            "plot_image": plot_base64,
            "table_data": table_payload
        })
    except Exception as e:
        return jsonify({
            "stdout": stdout_buf.getvalue() + f"\n[提示: 表格輸出簡化: {str(e)}]",
            "plot_image": plot_base64,
            "table_data": None
        })


@app.route("/api/health_check", methods=["POST"])
def health_check():
    """Run automated Step 1 & Step 2 EDA scan on a table in its project database."""
    data = request.get_json() or {}
    table_name = data.get("table", "defects")
    target_col = data.get("target_col", "")
    f_name = resolve_folder_for_table(table_name, data.get("folder", ""))

    conn = get_db_connection(f_name)
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
        conn.close()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    if not target_col or target_col not in df.columns:
        target_col = df.columns[-1]

    vc = df[target_col].value_counts(dropna=False).head(20).sort_index()
    target_dist = [
        {
            "value": str(k),
            "count": int(v),
            "pct": round(float(v) / len(df) * 100.0, 2)
        }
        for k, v in vc.items()
    ]

    num_df = df.select_dtypes(include=[np.number])
    correlations = []
    if target_col in num_df.columns and num_df[target_col].nunique() > 1:
        corr_series = num_df.corr()[target_col].drop(target_col, errors="ignore").dropna()
        corr_sorted = corr_series.reindex(corr_series.abs().sort_values(ascending=False).index)
        for col_name, val in corr_sorted.items():
            correlations.append({
                "column": col_name,
                "correlation": round(float(val), 4),
                "abs_corr": round(abs(float(val)), 4),
                "is_key": bool(abs(float(val)) >= 0.1)
            })

    return jsonify({
        "table": table_name,
        "folder": f_name,
        "target_col": target_col,
        "row_count": len(df),
        "col_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_missing": int(df.isnull().sum().sum()),
        "target_distribution": target_dist,
        "correlations": correlations
    })


@app.route("/api/notes", methods=["GET", "POST"])
def handle_notes():
    """Load or save SQL/Python query notes in the project's own `saved_queries.json`."""
    table_name = request.args.get("table", "defects")
    folder_arg = request.args.get("folder", "").strip()

    if request.method == "GET":
        f_name = resolve_folder_for_table(table_name, folder_arg)
        notes_dict = load_all_notes_dict(f_name)
        if request.args.get("all_tables") == "1":
            return jsonify({"folder": f_name, "notes_dict": notes_dict})
        if table_name not in notes_dict:
            conn = get_db_connection(f_name)
            try:
                df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
                conn.close()
                notes_dict[table_name] = generate_starter_notes_for_table(df, table_name)
                save_all_notes_dict(notes_dict, f_name)
            except Exception:
                conn.close()
                notes_dict[table_name] = []
        return jsonify({"table": table_name, "folder": f_name, "notes": notes_dict.get(table_name, [])})

    data = request.get_json() or {}
    table_name = data.get("table", table_name)
    f_name = resolve_folder_for_table(table_name, data.get("folder", folder_arg))
    notes_dict = load_all_notes_dict(f_name)

    if "notes_dict" in data and isinstance(data["notes_dict"], dict):
        notes_dict.update(data["notes_dict"])
        save_all_notes_dict(notes_dict, f_name)
        return jsonify({"message": f"已儲存專案 `{f_name}` 全部筆記！", "folder": f_name})

    notes = data.get("notes", [])
    has_from_table = any(isinstance(n, dict) and "_fromTable" in n for n in notes)
    if has_from_table:
        grouped = {}
        for n in notes:
            t = n.get("_fromTable", table_name)
            if t not in grouped:
                grouped[t] = []
            n_clean = {k: v for k, v in n.items() if k != "_fromTable"}
            grouped[t].append(n_clean)
        for t, t_notes in grouped.items():
            notes_dict[t] = t_notes
        save_all_notes_dict(notes_dict, f_name)
        return jsonify({"message": f"已儲存專案 `{f_name}` 筆記庫！", "count": len(notes)})
    else:
        notes_dict[table_name] = notes
        save_all_notes_dict(notes_dict, f_name)
        return jsonify({"message": f"已儲存至專案 `{f_name}` 的專屬筆記庫 (`{table_name}`)！", "count": len(notes)})


@app.route("/api/reset_default_notes", methods=["POST"])
def reset_default_notes():
    """Regenerate starter SQL + Python queries for the specified table & target column in its project folder."""
    data = request.get_json() or {}
    table_name = data.get("table", "defects")
    target_col = data.get("target_col", "")
    f_name = resolve_folder_for_table(table_name, data.get("folder", ""))

    conn = get_db_connection(f_name)
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
        conn.close()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    starter_notes = generate_starter_notes_for_table(df, table_name, target_col=target_col)
    notes_dict = load_all_notes_dict(f_name)
    existing = notes_dict.get(table_name, [])

    starter_ids = {q["id"] for q in starter_notes}
    custom_queries = [q for q in existing if q.get("id") not in starter_ids and str(q.get("id", "")).startswith("note_")]
    merged = starter_notes + custom_queries
    notes_dict[table_name] = merged
    save_all_notes_dict(notes_dict, f_name)

    return jsonify({
        "notes": merged,
        "message": f"已為專案 `{f_name}/{table_name}` (主角: `{target_col or df.columns[-1]}`) 重新產生專屬 SQL + Python 分析範本！"
    })


if __name__ == "__main__":
    init_db_and_notes()
    print("====================================================")
    print(" 🚀 DataFlow Studio (SQL + Python Analytics) 已啟動！")
    print(" 👉 請打開瀏覽器前往: http://127.0.0.1:5000")
    print("====================================================")
    app.run(host="127.0.0.1", port=5000, debug=False)
