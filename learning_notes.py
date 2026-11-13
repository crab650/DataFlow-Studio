"""Runnable SQL/Python lessons for the manufacturing defects demo project.

The workbench loads the selected table as ``df`` in Python mode. SQL mode uses
SQLite and the default project exposes the same data as the ``defects`` table.
"""


def lesson(number, language, title, code, explanation, chart=None):
    return {
        "id": f"note_course_defects_{number:02d}_{language}",
        "lang": language,
        "title": f"{number:02d}｜{title}",
        "step_tag": "製造缺陷實作課程",
        "folder": "📚 製造缺陷｜SQL + Python 實作課程",
        "sql": code.strip(),
        "note": explanation.strip(),
        "chart_config": chart or {},
    }


DEFECTS_LEARNING_NOTES = [
    lesson(1, "sql", "SQL：先建立缺陷率基準線", """
-- COUNT(*) 是總筆數；AVG(0/1) 等於 1 的比例。
SELECT DefectStatus AS 缺陷狀態,
       COUNT(*) AS 筆數,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM defects), 2) AS 佔比百分比
FROM defects
GROUP BY DefectStatus
ORDER BY DefectStatus;
""", """
學習目標：分析任何風險因子之前，先知道整體基準。DefectStatus=1 代表有缺陷，0 代表無缺陷。
讀結果：目前資料預期有 3,240 筆，其中 1 約佔 84%。後面若某組的缺陷率也是 84%，它並未明顯高於全體。
SQL 重點：COUNT(*) 計算筆數；乘 100.0 可避免整數除法；GROUP BY 將 0、1 分開。
練習：把 ORDER BY 改成筆數由多到少，觀察類別不平衡。
注意：84% 是這份合成資料的分布，不能當作真實工廠的普遍缺陷率。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
""", {"type": "bar", "x_col": "缺陷狀態", "y1_col": "筆數", "y2_col": "佔比百分比"}),

    lesson(2, "python", "Python：資料體檢與基準線", """
print('筆數、欄數：', df.shape)
print('完全重複列：', int(df.duplicated().sum()))
print('總缺值：', int(df.isna().sum().sum()))
print('各欄缺值：')
print(df.isna().sum().to_string())

baseline = (df['DefectStatus'].value_counts(dropna=False)
            .rename_axis('DefectStatus').reset_index(name='筆數'))
baseline['佔比百分比'] = (baseline['筆數'] / len(df) * 100).round(2)
baseline.sort_values('DefectStatus')
""", """
學習目標：用 Pandas 重做上一則 SQL，並檢查資料品質。
讀結果：右下表的兩列應與 SQL 一致；若不一致，先檢查是否選錯資料表或資料更新後未重新載入。
Python 重點：df 是平台預先載入的資料表；isna() 看缺值；duplicated() 看整列重複；value_counts() 算類別筆數。最後一行是 DataFrame，平台會顯示為表格。
練習：再執行 df.describe().T，找出數值欄位的極端值。
注意：沒有缺值不代表資料品質已足夠；欄位可能在業務上有不合理數值。
參考：https://github.com/TimvdHoek/Predicting-Defect-Rates-in-Manufacturing-Using-Machine-Learning
"""),

    lesson(3, "sql", "SQL：正常與缺陷組的指標比較", """
SELECT DefectStatus AS 缺陷狀態,
       COUNT(*) AS 樣本數,
       ROUND(AVG(MaintenanceHours), 2) AS 平均維護時數,
       ROUND(AVG(ProductionVolume), 2) AS 平均生產量,
       ROUND(AVG(QualityScore), 2) AS 平均品質分數,
       ROUND(AVG(DefectRate), 2) AS 平均製程缺陷率,
       ROUND(AVG(SupplierQuality), 2) AS 平均供應商品質
FROM defects
GROUP BY DefectStatus
ORDER BY DefectStatus;
""", """
學習目標：比較有缺陷與無缺陷兩組的平均值，篩出值得深入看的欄位。
讀結果：請同時看「平均值差異」與「樣本數」。這份資料中，維護時數、生產量、品質分數的組間差異較明顯；供應商品質差異較小。
SQL 重點：GROUP BY DefectStatus 後，每個 AVG 都只計算該組。可逐一加上其他欄位，不必為每個欄位重新寫一整段查詢。
練習：加入 AVG(DowntimePercentage)，比較它的組間差異。
注意：這裡只是關聯，不足以推論「增加維護時數會造成缺陷」。維護時數也可能是發現問題後增加的。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
"""),

    lesson(4, "python", "Python：組間差異與分布圖", """
columns = ['MaintenanceHours', 'ProductionVolume', 'QualityScore',
           'DefectRate', 'SupplierQuality']
summary = df.groupby('DefectStatus')[columns].agg(['count', 'mean', 'median'])
print(summary.round(2).to_string())

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
sns.boxplot(data=df, x='DefectStatus', y='MaintenanceHours', ax=axes[0])
sns.boxplot(data=df, x='DefectStatus', y='QualityScore', ax=axes[1])
axes[0].set_title('MaintenanceHours by defect status')
axes[1].set_title('QualityScore by defect status')
plt.tight_layout()

df.groupby('DefectStatus')[columns].mean().round(2)
""", """
學習目標：在 SQL 的平均值之外，再看中位數與分布，避免平均值掩蓋重疊與離群值。
讀結果：箱型圖的中線是中位數，箱體表示中間一半樣本。即使兩組平均值不同，只要箱體大量重疊，單一欄位仍未必能準確分類。
Python 重點：groupby().agg() 可一次算多種摘要；Seaborn boxplot 顯示分布；平台會把 Matplotlib 圖顯示在 Python 結果區。
練習：把右圖改成 ProductionVolume，觀察是否比 QualityScore 更容易區分兩組。
注意：QualityScore 與 DefectRate 可能是檢驗後才得到的資訊；探索資料可以看，事前預測模型要先確認取得時間。
參考：https://github.com/TimvdHoek/Predicting-Defect-Rates-in-Manufacturing-Using-Machine-Learning
"""),

    lesson(5, "sql", "SQL：維護時數分段與樣本量", """
WITH bands AS (
    SELECT CASE WHEN MaintenanceHours <= 5 THEN '01｜0–5 小時'
                WHEN MaintenanceHours <= 10 THEN '02｜6–10 小時'
                WHEN MaintenanceHours <= 15 THEN '03｜11–15 小時'
                ELSE '04｜16 小時以上' END AS 維護區間,
           DefectStatus
    FROM defects
)
SELECT 維護區間, COUNT(*) AS 樣本數,
       SUM(DefectStatus) AS 缺陷筆數,
       ROUND(AVG(DefectStatus) * 100.0, 2) AS 缺陷率百分比
FROM bands
GROUP BY 維護區間
ORDER BY 維護區間;
""", """
學習目標：將連續數值切成容易理解的區間，找風險是否在某處改變。
讀結果：先看缺陷率，再看樣本數。樣本太少的高風險區間可能只是波動；與第 1 課約 84% 的全體基準比較才有意義。
SQL 重點：CASE WHEN 依順序分段；CTE（WITH bands）讓分段邏輯只寫一次；對 0/1 欄位取 AVG 就是缺陷比例。
練習：把 10 小時分界改為 8 或 12，觀察結論是否穩定。
注意：分界線是從同一批資料探索出來的，尚未經獨立資料驗證；不要把它當成確定的工程規則。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
""", {"type": "bar_line", "x_col": "維護區間", "y1_col": "缺陷率百分比", "y2_col": "樣本數"}),

    lesson(6, "python", "Python：分段圖與 95% 不確定區間", """
import numpy as np

bands = pd.cut(df['MaintenanceHours'], bins=[-np.inf, 5, 10, 15, np.inf],
               labels=['0–5', '6–10', '11–15', '16+'])
summary = (df.assign(維護區間=bands).groupby('維護區間', observed=True)['DefectStatus']
           .agg(樣本數='size', 缺陷筆數='sum', 缺陷率='mean').reset_index())
p = summary['缺陷率']
n = summary['樣本數']
z = 1.96
center = (p + z*z/(2*n)) / (1 + z*z/n)
margin = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
summary['缺陷率百分比'] = (p * 100).round(2)
summary['95%下界'] = ((center - margin) * 100).round(2)
summary['95%上界'] = ((center + margin) * 100).round(2)

plt.figure(figsize=(8, 4))
plt.errorbar(summary['維護區間'].astype(str), summary['缺陷率百分比'],
             yerr=[summary['缺陷率百分比']-summary['95%下界'],
                   summary['95%上界']-summary['缺陷率百分比']], fmt='o-', capsize=5)
plt.axhline(df['DefectStatus'].mean() * 100, color='gray', linestyle='--', label='Overall baseline')
plt.ylabel('Defect rate (%)')
plt.xlabel('Maintenance hours')
plt.legend()
plt.tight_layout()
summary
""", """
學習目標：把 SQL 的分段結果畫出來，並顯示比例估計的不確定性。
讀結果：灰色虛線是全體缺陷率；圓點是每組缺陷率；上下誤差線是 Wilson 95% 區間。區間越寬，通常代表該組樣本越少或比例越不穩定。
Python 重點：pd.cut 對應 SQL 的 CASE WHEN；groupby.agg 算筆數與平均；Wilson 區間比直接使用常態近似更適合接近 0% 或 100% 的比例。
練習：改成以 QualityScore 分段，觀察低分組的缺陷率與樣本數。
注意：95% 區間只反映抽樣波動，不能消除合成資料偏差，也不能證明因果。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
"""),

    lesson(7, "sql", "SQL：三項風險訊號交叉驗證", """
WITH signals AS (
    SELECT DefectStatus,
           (CASE WHEN MaintenanceHours > 10 THEN 1 ELSE 0 END +
            CASE WHEN QualityScore < 75 THEN 1 ELSE 0 END +
            CASE WHEN ProductionVolume > 800 THEN 1 ELSE 0 END) AS 訊號數
    FROM defects
)
SELECT 訊號數, COUNT(*) AS 樣本數,
       SUM(DefectStatus) AS 缺陷筆數,
       ROUND(AVG(DefectStatus) * 100.0, 2) AS 缺陷率百分比
FROM signals
GROUP BY 訊號數
ORDER BY 訊號數;
""", """
學習目標：驗證幾個已發現的條件是否能組成可讀的風險規則。
讀結果：觀察 0、1、2、3 個訊號各有多少樣本與多高缺陷率。缺陷率不一定隨訊號數嚴格單調增加；請同時檢查每組樣本數。
SQL 重點：SQLite 中每個 CASE WHEN 產生 0/1，三項相加得到訊號數；CTE 讓後續 GROUP BY 更簡潔。
練習：把 MaintenanceHours > 10 改成 > 12，比較各組樣本數和缺陷率。
注意：這是回頭描述同一批資料，尚不是對未來樣本的預測能力。QualityScore 是否能在決策當下取得，也必須先確認。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
""", {"type": "bar_line", "x_col": "訊號數", "y1_col": "缺陷率百分比", "y2_col": "樣本數"}),

    lesson(8, "python", "Python：規則覆蓋率、精確率與召回率", """
rule = ((df['MaintenanceHours'] > 10) |
        (df['QualityScore'] < 75) |
        (df['ProductionVolume'] > 800))
y = df['DefectStatus'].astype(int)
tp = int((rule & (y == 1)).sum())
fp = int((rule & (y == 0)).sum())
fn = int((~rule & (y == 1)).sum())
tn = int((~rule & (y == 0)).sum())
print('TP=', tp, 'FP=', fp, 'FN=', fn, 'TN=', tn)

metrics = pd.DataFrame([{
    '規則': '三項訊號任一成立',
    '標記比例': round(rule.mean() * 100, 2),
    '精確率': round(tp / (tp + fp), 3) if tp + fp else 0,
    '召回率': round(tp / (tp + fn), 3) if tp + fn else 0,
    '整體準確率': round((tp + tn) / len(df), 3),
    '全判缺陷的基準準確率': round(y.mean(), 3)
}])
metrics
""", """
學習目標：從「高風險組缺陷率」進一步檢查規則的實際分類表現。
讀結果：TP 是正確標出的缺陷；FP 是誤報；FN 是漏報；TN 是正確排除。精確率=TP/(TP+FP)，召回率=TP/(TP+FN)。標記比例說明規則會要求檢查多少樣本。
Python 重點：| 代表「任一條件成立」；若要三項都成立，改用 &。比較全判缺陷的基準準確率，避免被高準確率誤導。
練習：將 | 改成 &，觀察誤報、漏報如何交換。
注意：這些門檻是在同一份資料上挑出的，這一則是教學示範，不可當作獨立測試績效。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
"""),

    lesson(9, "sql", "SQL：規則的混淆矩陣", """
WITH predictions AS (
    SELECT DefectStatus AS 實際,
           CASE WHEN MaintenanceHours > 10 OR QualityScore < 75 OR ProductionVolume > 800
                THEN 1 ELSE 0 END AS 預測
    FROM defects
)
SELECT 實際, 預測, COUNT(*) AS 筆數
FROM predictions
GROUP BY 實際, 預測
ORDER BY 實際 DESC, 預測 DESC;
""", """
學習目標：用 SQL 檢查第 8 課的 TP、FP、FN、TN，學會從資料列追溯模型指標。
讀結果：實際=1且預測=1 是 TP；實際=0且預測=1 是 FP；實際=1且預測=0 是 FN；實際=0且預測=0 是 TN。四格筆數加總應為 3,240。
SQL 重點：CASE WHEN 把規則變成 0/1 預測，再用兩個欄位 GROUP BY 形成混淆矩陣。
練習：用 SUM(CASE WHEN 實際=1 AND 預測=1 THEN 筆數 ELSE 0 END) 從四格加總 TP。
注意：與上一課相同，這仍是在探索用的資料上評估；需要留出測試才能估計泛化能力。
參考：https://github.com/khanabu03/manufacturing-defect-risk-analysis
"""),

    lesson(10, "python", "Python：留出測試與資料洩漏檢查", """
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             precision_score, recall_score, confusion_matrix)

# 只選示範性的操作欄位；確認實務上預測當下都已可取得。
features = ['ProductionVolume', 'SupplierQuality', 'DeliveryDelay',
            'MaintenanceHours', 'DowntimePercentage', 'WorkerProductivity',
            'EnergyConsumption']
X = df[features].copy()
y = df['DefectStatus'].astype(int)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=42)
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight='balanced'))
model.fit(X_train, y_train)
pred = model.predict(X_test)
tn, fp, fn, tp = confusion_matrix(y_test, pred, labels=[0, 1]).ravel()

results = pd.DataFrame([{
    '測試筆數': len(y_test),
    '全判缺陷準確率': round(y_test.mean(), 3),
    '模型準確率': round(accuracy_score(y_test, pred), 3),
    '平衡準確率': round(balanced_accuracy_score(y_test, pred), 3),
    '缺陷精確率': round(precision_score(y_test, pred, zero_division=0), 3),
    '缺陷召回率': round(recall_score(y_test, pred, zero_division=0), 3),
    'FP誤報': int(fp), 'FN漏報': int(fn)
}])
results
""", """
學習目標：只在訓練集學習模型，再用未參與訓練的 25% 資料評估；同時與「全部判為缺陷」基準比較。
讀結果：這份資料有約 84% 的缺陷樣本，所以只看準確率容易誤判。平衡準確率、精確率、召回率、誤報 FP 與漏報 FN 應一起看。
Python 重點：stratify=y 保持兩組比例；StandardScaler 放在 Pipeline 中，只從訓練資料估計縮放參數；class_weight='balanced' 讓較少的正常類別在訓練時也受重視。
資料洩漏檢查：DefectRate、QualityScore 可能是產品檢驗後結果，故示範模型先排除。OrderID、SupplierID、MachineID 是此專案程式後來合成的 ERP 欄位，也不應當成真實來源訊號。
限制：這是合成且沒有原始時間／真實機台 ID 的資料，隨機留出測試只能當入門練習，不能證明模型能預測真實工廠的未來缺陷。
練習：刪除 MaintenanceHours 重跑，比較召回率與誤報數，思考它是否是事前可取得的欄位。
參考：https://github.com/TimvdHoek/Predicting-Defect-Rates-in-Manufacturing-Using-Machine-Learning
"""),
]


def install_defects_lessons(notes_path):
    """Add missing lessons without changing notes the user has already edited."""
    import json
    import os
    import shutil
    from pathlib import Path

    path = Path(notes_path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError("筆記檔格式不是專案筆記字典，已停止寫入")
    existing = data.get("defects", [])
    if not isinstance(existing, list):
        raise ValueError("defects 筆記格式不正確，已停止寫入")
    existing_ids = {note.get("id") for note in existing if isinstance(note, dict)}
    additions = [note for note in DEFECTS_LEARNING_NOTES if note["id"] not in existing_ids]
    if not additions:
        return 0
    data["defects"] = existing + additions
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.with_suffix(".json.bak").exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    pending = path.with_suffix(".json.tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(pending, path)
    return len(additions)


if __name__ == "__main__":
    from pathlib import Path

    project = "01_Manufacturing_Quality_ERP"
    notes_file = Path(__file__).parent / "system_data" / project / "saved_queries.json"
    print(f"Installed {install_defects_lessons(notes_file)} manufacturing lessons")
