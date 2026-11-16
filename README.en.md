# DataFlow Studio

[繁體中文](README.md) | English

**DataFlow Studio** is a local SQL and Python data analysis workbench. It imports each dataset into a project specific SQLite database so you can inspect columns, run queries, analyze data with Pandas, create charts, and save reusable learning notes in one web interface.

The project is built for learning by doing: inspect the data, ask a question, test it with SQL or Python, and record both the finding and its limitations.

## Features

- **Separate project workspaces:** Each `datasets/<project>/` folder has its own `system_data/<project>/workspace.db` database.
- **SQL and Python modes:** Run SQLite queries or analyze the selected table as a Pandas DataFrame named `df`. The `tables` helper loads other tables from the same project.
- **Data import and preparation:** Import CSV or Excel files, scan dataset folders, upload multiple files, and join or concatenate tables in the interface.
- **Charts and results:** Create dual axis charts from SQL results or return DataFrames, text, and Matplotlib or Seaborn plots from Python.
- **Saved learning notes:** Keep code, explanations, categories, and chart settings. Each project also has an English and Chinese column dictionary.

## Quick start

The project has been used on **Windows with Python 3.12**. Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

From the project root, run:

```bash
python app.py
```

On Windows, you can also double click `start_DataFlow_Studio.bat`. Open **http://127.0.0.1:5000** after the server starts. The interface loads Tailwind CSS, Chart.js, and CodeMirror from CDNs, so it needs access to those services.

The GitHub repository includes the demo CSVs, learning notes, and column dictionaries. SQLite `workspace.db` files are rebuilt from the CSVs on first launch, which may take a little time.

### Run your first analysis

1. Choose a **project folder** and a **table** at the top of the page.
2. Inspect the column dictionary or select a learning note from the left sidebar. Click Run or press `Ctrl+Enter`.
3. Write SQLite queries in SQL mode. In Python mode, you can use `df`, `tables`, `pd`, `np`, `plt`, and `sns`.
4. Review the resulting table or chart, then save your observations as a note.

For example, select the `superstoreorders` table in the Superstore project and run:

```sql
SELECT category,
       COUNT(*) AS item_rows,
       ROUND(SUM(sales), 2) AS total_sales,
       ROUND(SUM(profit), 2) AS total_profit
FROM superstoreorders
GROUP BY category
ORDER BY total_sales DESC;
```

In Python mode, you can analyze the same table with:

```python
df.groupby('category')[['sales', 'profit']].sum().round(2)
```

## Data analysis projects

**Each row represents one dataset analysis project.** Its SQL work, Python work, notes, and column dictionary stay in the same row.

| No. | Analysis project | Data and analysis | Completed learning material | Where to find it |
|---|---|---|---|---|
| 01 | Manufacturing Defects and Demo ERP | 3,240 `defects` records and three tables in total, including demo supplier and machine tables; explores defect rates, risk conditions, and model evaluation | 10 SQL and Python lessons; 32 column descriptions | Select `01_Manufacturing_Quality_ERP` → `defects`; [course guide](docs/manufacturing_defects_course.md) |
| 02 | Global Superstore Sales | 51,290 `superstoreorders` rows; explores sales, profit, categories, geography, and discounts | 30 SQL and Python notes, including eight ST1 beginner lessons; 21 column descriptions | Select `02_Superstore_Sales` → `superstoreorders` |
| 03 | Olist Brazilian E-Commerce | Eight core tables, including 99,441 orders; explores customers, items, payments, reviews, and repeat purchases | 12 focused SQL lessons (20 notes on the orders table in total); 47 column descriptions | Select `03_Olist_Brazilian_Ecommerce` → `olist_orders_dataset`; [course guide](docs/olist_sql_course.md) |
| 04 | Hotel Booking Demand & Cancellations | 119,390 `hotel_bookings` rows; explores cancellation leakage, seasonal ADR pricing, 90-day lead time thresholds, front desk BI cockpit, and frontline daily operational run sheets | 19 beginner-friendly SQL and Python tutorial notes across 7 thematic folders (including Front Office BI and frontline daily operational sheets); 32 column descriptions | Select `04_Hotel_Booking_Analytics` → `hotel_bookings` |
| 05 | Coffee Shop Sales & Store Operations | 149,116 `coffee_shop_sales` rows; explores morning peak hour barista capacity, category Pareto 80/20, breakfast attachment rates, and store manager daily staffing BI | 10 beginner-friendly SQL and Python tutorial notes across 5 thematic folders; 12 column descriptions | Select `05_Coffee_Shop_Sales` → `coffee_shop_sales` |

**How this table is maintained:** Add one numbered row when a new dataset analysis project is created. Platform features, individual files, lessons, and dictionaries belong to their dataset project and do not get separate rows. Update an existing row when more analysis is added to that project. The rule is also recorded in `AGENTS.md`.

## Add your own data

**Option 1: Scan a folder.** Create a project folder under `datasets/`, add one or more `.csv`, `.xlsx`, or `.xls` files, and click Scan in the interface. DataFlow Studio creates a separate SQLite database and starter notes. If a source file changes later, scan again to update its table while keeping saved notes. When upgrading an existing database, the first fingerprint scan preserves any previous table edits.

**Option 2: Upload in the browser.** Use Import Data in the upper right corner. You can name the project and import one or more files as separate tables or concatenate them.

To recreate the eight Olist tables, run `python scripts/import_olist.py`. It downloads data from the [official Kaggle dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The large geolocation table is outside the scope of this beginner course. Run `python olist_sql_lessons.py` and `python olist_column_dictionary.py` to restore missing lessons or column definitions without overwriting existing edits.

## Project structure

```text
app.py                     Flask API, imports, SQL/Python execution, starter notes
templates/index.html       Web workbench
datasets/                  Original CSV and Excel files, grouped by project
system_data/               Per-project SQLite databases, notes, dictionaries, fingerprints
learning_notes.py          Manufacturing defects lessons
olist_sql_lessons.py        Olist SQL lessons
olist_column_dictionary.py Olist bilingual column dictionary
scripts/import_olist.py    Official Olist dataset importer
docs/                      Course guides
tests/                     Data safety and lesson execution tests
```

After importing the Olist data, run the tests with:

```bash
python -m unittest discover -s tests -v
```

## Data sources and scope

- The original manufacturing CSV comes from the [Predicting Manufacturing Defects Dataset](https://www.kaggle.com/datasets/rabieelkharoua/predicting-manufacturing-defects-dataset). The `OrderID`, `SupplierID`, and `MachineID` fields and companion tables in this project are generated demo ERP data, not real records from the source dataset.
- The 21-column Superstore version corresponds to [SuperStore Sales Analytics](https://www.kaggle.com/datasets/thuandao/superstore-sales-analytics).
- The Olist data comes from the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The Kaggle API labels its license **CC BY-NC-SA 4.0**. See `datasets/03_Olist_Brazilian_Ecommerce/SOURCE.md` for provenance and import scope.
- The Hotel Booking Demand dataset comes from [Hotel Booking Demand](https://www.kaggle.com/datasets/jessemostipak/hotel-booking-demand) (Antonio et al., 2019), licensed under **CC0: Public Domain**. See `datasets/04_Hotel_Booking_Analytics/SOURCE.md` for details.
- The Coffee Shop Sales dataset comes from [Coffee Shop Sales Analysis](https://raw.githubusercontent.com/thedatanook/Coffee-Shop-Sales-Analysis/main/Coffee%20Shop%20Sales.csv) (Maven Analytics). See `datasets/05_Coffee_Shop_Sales/SOURCE.md` for details.

Each dataset folder has a `SOURCE.md` documenting its source and license. This repository does not declare an open source license for the application code; follow each dataset's license separately.

By default, the server listens only on `127.0.0.1`. The Python editor executes user supplied code, so use this workbench in a trusted local environment. It does not provide accounts, access controls, or a public deployment setup. Relationships observed in the demo datasets should not be treated as causal conclusions.
