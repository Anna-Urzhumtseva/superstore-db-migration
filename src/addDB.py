
import pandas as pd
import sqlite3
from pathlib import Path

# Пути к файлам
BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILE = BASE_DIR / "data" / "sqlite" / "old_database.db"
EXCEL_FILE = BASE_DIR / "data" / "raw" / "Sample_-_Superstore.xlsx"

# Подключаемся к базе
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Загружаем Excel
df_orders = pd.read_excel(EXCEL_FILE, sheet_name='Orders')
df_people = pd.read_excel(EXCEL_FILE, sheet_name='People')
df_returns = pd.read_excel(EXCEL_FILE, sheet_name='Returns')

# Убираем дубли в People и Returns (чтобы не было ошибок PRIMARY KEY)
df_people_unique = df_people.drop_duplicates(subset=['Region'], keep='first')
df_returns_unique = df_returns.drop_duplicates(subset=['Order ID'], keep='first')

# Создаём таблицы (старая структура)
cursor.executescript('''
    DROP TABLE IF EXISTS Orders;
    DROP TABLE IF EXISTS People;
    DROP TABLE IF EXISTS Returns;

    CREATE TABLE Orders (
        "Row ID" INTEGER PRIMARY KEY AUTOINCREMENT,
        "Order ID" TEXT,
        "Order Date" TEXT,
        "Ship Date" TEXT,
        "Ship Mode" TEXT,
        "Customer ID" TEXT,
        "Customer Name" TEXT,
        "Segment" TEXT,
        "Country/Region" TEXT,
        "City" TEXT,
        "State" TEXT,
        "Postal Code" TEXT,
        "Region" TEXT,
        "Product ID" TEXT,
        "Category" TEXT,
        "Sub-Category" TEXT,
        "Product Name" TEXT,
        "Sales" REAL,
        "Quantity" INTEGER,
        "Discount" REAL,
        "Profit" REAL
    );

    CREATE TABLE People (
        "Person" TEXT,
        "Region" TEXT PRIMARY KEY
    );

    CREATE TABLE Returns (
        "Returned" TEXT,
        "Order ID" TEXT PRIMARY KEY
    );
''')

# Загружаем данные
df_orders.to_sql('Orders', conn, if_exists='append', index=False)
df_people_unique.to_sql('People', conn, if_exists='append', index=False)
df_returns_unique.to_sql('Returns', conn, if_exists='append', index=False)

conn.commit()
conn.close()

print("✅ Старая база old_database.db создана!")