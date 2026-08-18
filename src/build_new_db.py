"""
build_new_db.py
================
Полностью автоматическая сборка нормализованной SQLite-базы
из исходного плоского файла Sample_-_Superstore_format.xlsx.

Заменяет собой цепочку:
    addDB.py -> transform_data.sql (вручную, по одной CTE) ->
    ручная сборка Sample_-_Superstore_MODIFICATED.xlsx -> addNewDB.py

Теперь всё происходит в одном скрипте, без ручного шага в Excel,
поэтому ошибка, при которой Profit "уезжал" на порядки (см. разбор
в чате), больше не может возникнуть — Sales/Discount/Profit
никогда не покидают SQL/pandas и не проходят через ручное
копирование в Excel.

Использование:
    python build_new_db.py

Ожидает структуру проекта как в остальных скриптах репозитория
(скрипт лежит в src/, данные — на уровень выше):

    project_root/
    ├── data/
    │   ├── raw/
    │   │   └── Sample_-_Superstore_format.xlsx
    │   └── sqlite/
    │       └── newdatabase.db   <- создаётся этим скриптом
    └── src/
        └── build_new_db.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Как в addDB.py / addNewDB.py: скрипт лежит в src/, поэтому корень
# проекта — на уровень выше (.parent.parent от файла скрипта).
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_EXCEL = BASE_DIR / "data" / "raw" / "Sample_-_Superstore_format.xlsx"
NEW_DB = BASE_DIR / "data" / "sqlite" / "newdatabase.db"

# Контрольные суммы из исходного файла — используются для финальной
# проверки, что при трансформации ничего не потерялось и не исказилось.
EXPECTED_ROWS = {
    "Product": 1894,
    "People": 4,
    "typeShip": 4,
    "Addresses": 632,
    "Customers": 793,
    "Orders": 5009,
    "dateShip": 5009,
    "OrderDetails": 9993,
    "Returns": 800,
}
EXPECTED_TOTAL_PROFIT = 286409.08  # сумма по 9993 строкам без дубля Row ID 3406/3407
EXPECTED_TOTAL_SALES = 2296919.49
TOLERANCE = 1.0  # допустимое отклонение суммы Profit/Sales из-за округления float

SCHEMA_SQL = """
CREATE TABLE Product (
    ProductCode INTEGER PRIMARY KEY AUTOINCREMENT,
    ProductID TEXT,
    Category TEXT,
    SubCategory TEXT,
    ProductName TEXT
);
CREATE TABLE People (
    PeopleID INTEGER PRIMARY KEY AUTOINCREMENT,
    Person TEXT,
    Region TEXT
);
CREATE TABLE Customers (
    CustomerID TEXT PRIMARY KEY,
    CustomerName TEXT,
    Segment TEXT
);
CREATE TABLE typeShip (
    ShipID INTEGER PRIMARY KEY AUTOINCREMENT,
    ShipMode TEXT
);
CREATE TABLE Addresses (
    AddressesID INTEGER PRIMARY KEY AUTOINCREMENT,
    Country TEXT,
    City TEXT,
    State TEXT,
    PostalCode TEXT
);
CREATE TABLE Orders (
    OrderID TEXT PRIMARY KEY,
    OrderDate TEXT,
    PeopleID INTEGER,
    CustomerID TEXT,
    ShipID INTEGER,
    AddressesID INTEGER,
    FOREIGN KEY (PeopleID) REFERENCES People(PeopleID),
    FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    FOREIGN KEY (ShipID) REFERENCES typeShip(ShipID),
    FOREIGN KEY (AddressesID) REFERENCES Addresses(AddressesID)
);
CREATE TABLE dateShip (
    dateShipID INTEGER PRIMARY KEY AUTOINCREMENT,
    ShipID INTEGER,
    OrderID TEXT,
    ShipDate TEXT,
    FOREIGN KEY (ShipID) REFERENCES typeShip(ShipID),
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);
CREATE TABLE OrderDetails (
    DetailID INTEGER PRIMARY KEY AUTOINCREMENT,
    OrderID TEXT,
    ProductCode INTEGER,
    Quantity INTEGER,
    Sales REAL,
    Discount REAL,
    Profit REAL,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
    FOREIGN KEY (ProductCode) REFERENCES Product(ProductCode)
);
CREATE TABLE Returns (
    ReturnID INTEGER PRIMARY KEY AUTOINCREMENT,
    Returned TEXT,
    DetailID INTEGER,
    FOREIGN KEY (DetailID) REFERENCES OrderDetails(DetailID)
);
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def load_raw_into_staging(conn: sqlite3.Connection) -> None:
    """Читает сырой Excel и кладёт его as-is во временные staging-таблицы
    внутри той же базы. Ничего не считается руками, никакого Excel
    после этого шага больше не открывается."""
    log("📥 Читаю Sample_-_Superstore_format.xlsx (Orders, People, Returns)...")
    df_orders = pd.read_excel(RAW_EXCEL, sheet_name="Orders")
    df_people = pd.read_excel(RAW_EXCEL, sheet_name="People")
    df_returns = pd.read_excel(RAW_EXCEL, sheet_name="Returns")

    # Приводим даты к единому текстовому формату сразу, без формул Excel
    df_orders["Order Date"] = pd.to_datetime(df_orders["Order Date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_orders["Ship Date"] = pd.to_datetime(df_orders["Ship Date"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    df_orders.to_sql("_raw_orders", conn, index=False, if_exists="replace")
    df_people.to_sql("_raw_people", conn, index=False, if_exists="replace")
    df_returns.to_sql("_raw_returns", conn, index=False, if_exists="replace")
    log(f"   Orders: {len(df_orders)} строк, People: {len(df_people)}, Returns: {len(df_returns)}")


def build_schema(conn: sqlite3.Connection) -> None:
    log("🧱 Создаю схему новой БД (9 таблиц + FOREIGN KEY)...")
    conn.executescript(SCHEMA_SQL)


def populate_tables(conn: sqlite3.Connection) -> None:
    """Прямой аналог transform_data.sql, но вместо одного SELECT в конце —
    9 INSERT INTO ... SELECT, каждый сразу пишет в целевую таблицу."""
    cur = conn.cursor()

    log("🔧 Product...")
    cur.execute("""
        INSERT INTO Product (ProductID, Category, SubCategory, ProductName)
        SELECT DISTINCT
            "Product ID",
            Category,
            "Sub-Category",
            "Product Name"
        FROM _raw_orders
        ORDER BY "Product ID", "Product Name"
    """)

    log("🔧 Addresses...")
    cur.execute("""
        INSERT INTO Addresses (Country, City, State, PostalCode)
        SELECT DISTINCT
            "Country/Region",
            City,
            State,
            IFNULL("Postal Code", '00000') AS PostalCode
        FROM _raw_orders
        ORDER BY "Country/Region", State, City, PostalCode
    """)

    log("🔧 typeShip...")
    cur.execute("""
        INSERT INTO typeShip (ShipMode)
        SELECT DISTINCT "Ship Mode"
        FROM _raw_orders
        ORDER BY "Ship Mode"
    """)

    log("🔧 People...")
    cur.execute("""
        INSERT INTO People (Person, Region)
        SELECT DISTINCT Person, Region
        FROM _raw_people
        ORDER BY Region, Person
    """)

    log("🔧 Customers...")
    cur.execute("""
        INSERT INTO Customers (CustomerID, CustomerName, Segment)
        SELECT DISTINCT
            "Customer ID",
            "Customer Name",
            Segment
        FROM _raw_orders
    """)

    log("🔧 Orders...")
    cur.execute("""
        INSERT INTO Orders (OrderID, OrderDate, PeopleID, CustomerID, ShipID, AddressesID)
        SELECT DISTINCT
            o."Order ID",
            o."Order Date",
            p.PeopleID,
            o."Customer ID",
            ts.ShipID,
            a.AddressesID
        FROM _raw_orders o
        LEFT JOIN People p  ON p.Region = o.Region
        LEFT JOIN typeShip ts ON ts.ShipMode = o."Ship Mode"
        LEFT JOIN Addresses a ON a.Country = o."Country/Region"
                              AND a.City = o.City
                              AND a.State = o.State
                              AND a.PostalCode = IFNULL(o."Postal Code", '00000')
        ORDER BY o."Order Date", o."Customer ID", o."Order ID"
    """)

    log("🔧 dateShip...")
    cur.execute("""
        INSERT INTO dateShip (ShipID, OrderID, ShipDate)
        SELECT DISTINCT
            ts.ShipID,
            o."Order ID",
            o."Ship Date"
        FROM _raw_orders o
        LEFT JOIN typeShip ts ON ts.ShipMode = o."Ship Mode"
        ORDER BY o."Order ID"
    """)

    log("🔧 OrderDetails (Sales/Discount/Profit напрямую из исходника)...")
    cur.execute("""
        INSERT INTO OrderDetails (OrderID, ProductCode, Quantity, Sales, Discount, Profit)
        SELECT DISTINCT
            o."Order ID",
            p.ProductCode,
            o.Quantity,
            o.Sales,
            o.Discount,
            o.Profit
        FROM _raw_orders o
        LEFT JOIN Product p ON p.ProductID = o."Product ID"
                            AND p.ProductName = o."Product Name"
        ORDER BY o."Order ID"
    """)

    log("🔧 Returns...")
    cur.execute("""
        INSERT INTO Returns (Returned, DetailID)
        SELECT DISTINCT r.Returned, od.DetailID
        FROM _raw_returns r
        LEFT JOIN Orders o ON o.OrderID = r."Order ID"
        LEFT JOIN OrderDetails od ON od.OrderID = o.OrderID
        WHERE od.DetailID IS NOT NULL
        ORDER BY od.DetailID
    """)

    conn.commit()


def cleanup_staging(conn: sqlite3.Connection) -> None:
    log("🧹 Удаляю временные staging-таблицы...")
    conn.executescript("""
        DROP TABLE IF EXISTS _raw_orders;
        DROP TABLE IF EXISTS _raw_people;
        DROP TABLE IF EXISTS _raw_returns;
    """)
    conn.commit()


def validate(conn: sqlite3.Connection) -> bool:
    log("\n✅ ПРОВЕРКА РЕЗУЛЬТАТА")
    log("-" * 50)
    cur = conn.cursor()
    all_ok = True

    # 1. Количество строк по каждой таблице
    for table, expected in EXPECTED_ROWS.items():
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        actual = cur.fetchone()[0]
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_ok = False
        log(f"  {table:15s} ожидание={expected:6d}  факт={actual:6d}  [{status}]")

    # 2. Целостность внешних ключей (не должно быть orphan-записей)
    fk_checks = {
        "Orders.PeopleID -> People":       'SELECT COUNT(*) FROM Orders WHERE PeopleID NOT IN (SELECT PeopleID FROM People)',
        "Orders.CustomerID -> Customers":  'SELECT COUNT(*) FROM Orders WHERE CustomerID NOT IN (SELECT CustomerID FROM Customers)',
        "Orders.ShipID -> typeShip":       'SELECT COUNT(*) FROM Orders WHERE ShipID NOT IN (SELECT ShipID FROM typeShip)',
        "Orders.AddressesID -> Addresses": 'SELECT COUNT(*) FROM Orders WHERE AddressesID NOT IN (SELECT AddressesID FROM Addresses)',
        "OrderDetails.OrderID -> Orders":  'SELECT COUNT(*) FROM OrderDetails WHERE OrderID NOT IN (SELECT OrderID FROM Orders)',
        "OrderDetails.ProductCode -> Product": 'SELECT COUNT(*) FROM OrderDetails WHERE ProductCode NOT IN (SELECT ProductCode FROM Product)',
        "Returns.DetailID -> OrderDetails": 'SELECT COUNT(*) FROM Returns WHERE DetailID NOT IN (SELECT DetailID FROM OrderDetails)',
        "dateShip.OrderID -> Orders":      'SELECT COUNT(*) FROM dateShip WHERE OrderID NOT IN (SELECT OrderID FROM Orders)',
    }
    log("")
    for name, q in fk_checks.items():
        cur.execute(q)
        orphans = cur.fetchone()[0]
        status = "OK" if orphans == 0 else "ОШИБКА"
        if orphans != 0:
            all_ok = False
        log(f"  {name:35s} orphan-строк={orphans}  [{status}]")

    # 3. Контрольная сумма Sales/Profit (главная защита от бага с Profit)
    cur.execute("SELECT SUM(Sales), SUM(Profit) FROM OrderDetails")
    total_sales, total_profit = cur.fetchone()
    log("")
    sales_ok = abs(total_sales - EXPECTED_TOTAL_SALES) < TOLERANCE
    profit_ok = abs(total_profit - EXPECTED_TOTAL_PROFIT) < TOLERANCE
    log(f"  SUM(Sales)  ожидание={EXPECTED_TOTAL_SALES:,.2f}  факт={total_sales:,.2f}  [{'OK' if sales_ok else 'ОШИБКА'}]")
    log(f"  SUM(Profit) ожидание={EXPECTED_TOTAL_PROFIT:,.2f}  факт={total_profit:,.2f}  [{'OK' if profit_ok else 'ОШИБКА'}]")
    all_ok = all_ok and sales_ok and profit_ok

    log("-" * 50)
    log("🎉 ВСЁ СОШЛОСЬ, база собрана корректно." if all_ok else "⚠️  ЕСТЬ РАСХОЖДЕНИЯ, см. выше.")
    return all_ok


def main() -> int:
    if not RAW_EXCEL.exists():
        log(f"❌ Не найден исходный файл: {RAW_EXCEL}")
        log("   Проверьте, что Sample_-_Superstore_format.xlsx лежит в data/raw/")
        return 1

    NEW_DB.parent.mkdir(parents=True, exist_ok=True)  # создаст data/sqlite/, если его ещё нет
    if NEW_DB.exists():
        NEW_DB.unlink()

    conn = sqlite3.connect(NEW_DB)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_raw_into_staging(conn)
        build_schema(conn)
        populate_tables(conn)
        cleanup_staging(conn)
        ok = validate(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
