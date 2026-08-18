"""
build_new_db_postgres.py
=========================
Та же логика, что в build_new_db.py (сырой Excel -> нормализованная
БД, без ручного шага в Excel), но целевая СУБД — PostgreSQL, а не
SQLite.

Требуются пакеты:
    pip install pandas openpyxl sqlalchemy psycopg2-binary

Параметры подключения берутся из переменных окружения
(см. блок CONFIG ниже) — так удобнее и безопаснее, чем хардкодить
пароль в коде. Можно задать их прямо перед запуском:

    export PGHOST=localhost
    export PGPORT=5432
    export PGDATABASE=superstore
    export PGUSER=postgres
    export PGPASSWORD=secret
    python build_new_db_postgres.py

Целевая база (PGDATABASE) должна уже существовать — PostgreSQL,
в отличие от SQLite, не создаёт файл базы "на лету". Таблицы внутри
неё скрипт пересоздаёт с нуля сам (DROP + CREATE).

ВАЖНО: этот скрипт не был прогнан против живого PostgreSQL в среде,
где я его писала (нет доступа в сеть, чтобы поднять сервер) —
проверьте у себя и напишите, если что-то не заведётся с первого раза.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# CONFIG — как и в исходных addDB.py/addNewDB.py, скрипт лежит в src/,
# данные — на уровень выше.
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_EXCEL = BASE_DIR / "data" / "raw" / "Sample_-_Superstore_format.xlsx"

PG_HOST = os.environ.get("PGHOST", "localhost")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_DB = os.environ.get("PGDATABASE", "superstore")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD", "")

DB_URL = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

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
EXPECTED_TOTAL_PROFIT = 286409.08
EXPECTED_TOTAL_SALES = 2296919.49
TOLERANCE = 1.0

# ---------------------------------------------------------------------------
# Отличия от SQLite-версии схемы:
#   INTEGER PRIMARY KEY AUTOINCREMENT  ->  SERIAL / GENERATED ... AS IDENTITY
#   REAL                                ->  NUMERIC(12,4)  (без ошибок float-округления,
#                                            это и было одной из причин "уехавшего" Profit)
#   даты как TEXT                       ->  TIMESTAMP (нативный тип, можно фильтровать
#                                            по датам средствами SQL, а не строками)
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
DROP TABLE IF EXISTS "Returns"      CASCADE;
DROP TABLE IF EXISTS "OrderDetails" CASCADE;
DROP TABLE IF EXISTS "dateShip"     CASCADE;
DROP TABLE IF EXISTS "Orders"       CASCADE;
DROP TABLE IF EXISTS "Product"      CASCADE;
DROP TABLE IF EXISTS "Addresses"    CASCADE;
DROP TABLE IF EXISTS "Customers"    CASCADE;
DROP TABLE IF EXISTS "People"       CASCADE;
DROP TABLE IF EXISTS "typeShip"     CASCADE;

CREATE TABLE "Product" (
    "ProductCode" SERIAL PRIMARY KEY,
    "ProductID"   TEXT,
    "Category"    TEXT,
    "SubCategory" TEXT,
    "ProductName" TEXT
);

CREATE TABLE "People" (
    "PeopleID" SERIAL PRIMARY KEY,
    "Person"   TEXT,
    "Region"   TEXT
);

CREATE TABLE "Customers" (
    "CustomerID"   TEXT PRIMARY KEY,
    "CustomerName" TEXT,
    "Segment"      TEXT
);

CREATE TABLE "typeShip" (
    "ShipID"   SERIAL PRIMARY KEY,
    "ShipMode" TEXT
);

CREATE TABLE "Addresses" (
    "AddressesID" SERIAL PRIMARY KEY,
    "Country"     TEXT,
    "City"        TEXT,
    "State"       TEXT,
    "PostalCode"  TEXT
);

CREATE TABLE "Orders" (
    "OrderID"      TEXT PRIMARY KEY,
    "OrderDate"    TIMESTAMP,
    "PeopleID"     INTEGER REFERENCES "People"("PeopleID"),
    "CustomerID"   TEXT    REFERENCES "Customers"("CustomerID"),
    "ShipID"       INTEGER REFERENCES "typeShip"("ShipID"),
    "AddressesID"  INTEGER REFERENCES "Addresses"("AddressesID")
);

CREATE TABLE "dateShip" (
    "dateShipID" SERIAL PRIMARY KEY,
    "ShipID"     INTEGER REFERENCES "typeShip"("ShipID"),
    "OrderID"    TEXT    REFERENCES "Orders"("OrderID"),
    "ShipDate"   TIMESTAMP
);

CREATE TABLE "OrderDetails" (
    "DetailID"    SERIAL PRIMARY KEY,
    "OrderID"     TEXT    REFERENCES "Orders"("OrderID"),
    "ProductCode" INTEGER REFERENCES "Product"("ProductCode"),
    "Quantity"    INTEGER,
    "Sales"       NUMERIC(12,4),
    "Discount"    NUMERIC(6,4),
    "Profit"      NUMERIC(12,4)
);

CREATE TABLE "Returns" (
    "ReturnID" SERIAL PRIMARY KEY,
    "Returned" TEXT,
    "DetailID" INTEGER REFERENCES "OrderDetails"("DetailID")
);
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def load_raw_into_staging(engine) -> None:
    log("📥 Читаю Sample_-_Superstore_format.xlsx (Orders, People, Returns)...")
    df_orders = pd.read_excel(RAW_EXCEL, sheet_name="Orders")
    df_people = pd.read_excel(RAW_EXCEL, sheet_name="People")
    df_returns = pd.read_excel(RAW_EXCEL, sheet_name="Returns")

    df_orders["Order Date"] = pd.to_datetime(df_orders["Order Date"])
    df_orders["Ship Date"] = pd.to_datetime(df_orders["Ship Date"])

    # Zip-код: сохраняем 5-значный текстовый формат с ведущими нулями
    # (в отличие от старой версии, где это терялось при хранении как число).
    df_orders["Postal Code"] = (
        df_orders["Postal Code"].fillna(0).astype(int).astype(str).str.zfill(5)
    )

    df_orders.to_sql("_raw_orders", engine, index=False, if_exists="replace")
    df_people.to_sql("_raw_people", engine, index=False, if_exists="replace")
    df_returns.to_sql("_raw_returns", engine, index=False, if_exists="replace")
    log(f"   Orders: {len(df_orders)} строк, People: {len(df_people)}, Returns: {len(df_returns)}")


def build_schema(conn) -> None:
    log("🧱 Создаю схему новой БД (9 таблиц + FOREIGN KEY)...")
    conn.execute(text(SCHEMA_SQL))


def populate_tables(conn) -> None:
    log("🔧 Product...")
    conn.execute(text("""
        INSERT INTO "Product" ("ProductID", "Category", "SubCategory", "ProductName")
        SELECT DISTINCT
            "Product ID",
            "Category",
            "Sub-Category",
            "Product Name"
        FROM _raw_orders
    """))

    log("🔧 Addresses...")
    conn.execute(text("""
        INSERT INTO "Addresses" ("Country", "City", "State", "PostalCode")
        SELECT DISTINCT
            "Country/Region",
            "City",
            "State",
            COALESCE("Postal Code", '00000')
        FROM _raw_orders
    """))

    log("🔧 typeShip...")
    conn.execute(text("""
        INSERT INTO "typeShip" ("ShipMode")
        SELECT DISTINCT "Ship Mode"
        FROM _raw_orders
    """))

    log("🔧 People...")
    conn.execute(text("""
        INSERT INTO "People" ("Person", "Region")
        SELECT DISTINCT "Person", "Region"
        FROM _raw_people
    """))

    log("🔧 Customers...")
    conn.execute(text("""
        INSERT INTO "Customers" ("CustomerID", "CustomerName", "Segment")
        SELECT DISTINCT
            "Customer ID",
            "Customer Name",
            "Segment"
        FROM _raw_orders
    """))

    log("🔧 Orders...")
    conn.execute(text("""
        INSERT INTO "Orders" ("OrderID", "OrderDate", "PeopleID", "CustomerID", "ShipID", "AddressesID")
        SELECT DISTINCT
            o."Order ID",
            o."Order Date",
            p."PeopleID",
            o."Customer ID",
            ts."ShipID",
            a."AddressesID"
        FROM _raw_orders o
        LEFT JOIN "People" p    ON p."Region" = o."Region"
        LEFT JOIN "typeShip" ts ON ts."ShipMode" = o."Ship Mode"
        LEFT JOIN "Addresses" a ON a."Country" = o."Country/Region"
                                AND a."City" = o."City"
                                AND a."State" = o."State"
                                AND a."PostalCode" = COALESCE(o."Postal Code", '00000')
    """))

    log("🔧 dateShip...")
    conn.execute(text("""
        INSERT INTO "dateShip" ("ShipID", "OrderID", "ShipDate")
        SELECT DISTINCT
            ts."ShipID",
            o."Order ID",
            o."Ship Date"
        FROM _raw_orders o
        LEFT JOIN "typeShip" ts ON ts."ShipMode" = o."Ship Mode"
    """))

    log("🔧 OrderDetails (Sales/Discount/Profit напрямую из исходника)...")
    conn.execute(text("""
        INSERT INTO "OrderDetails" ("OrderID", "ProductCode", "Quantity", "Sales", "Discount", "Profit")
        SELECT DISTINCT
            o."Order ID",
            p."ProductCode",
            o."Quantity",
            o."Sales",
            o."Discount",
            o."Profit"
        FROM _raw_orders o
        LEFT JOIN "Product" p ON p."ProductID" = o."Product ID"
                              AND p."ProductName" = o."Product Name"
    """))

    log("🔧 Returns...")
    conn.execute(text("""
        INSERT INTO "Returns" ("Returned", "DetailID")
        SELECT DISTINCT r."Returned", od."DetailID"
        FROM _raw_returns r
        LEFT JOIN "Orders" o ON o."OrderID" = r."Order ID"
        LEFT JOIN "OrderDetails" od ON od."OrderID" = o."OrderID"
        WHERE od."DetailID" IS NOT NULL
    """))


def cleanup_staging(conn) -> None:
    log("🧹 Удаляю временные staging-таблицы...")
    conn.execute(text('DROP TABLE IF EXISTS _raw_orders'))
    conn.execute(text('DROP TABLE IF EXISTS _raw_people'))
    conn.execute(text('DROP TABLE IF EXISTS _raw_returns'))


def validate(conn) -> bool:
    log("\n✅ ПРОВЕРКА РЕЗУЛЬТАТА")
    log("-" * 50)
    all_ok = True

    for table, expected in EXPECTED_ROWS.items():
        actual = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_ok = False
        log(f"  {table:15s} ожидание={expected:6d}  факт={actual:6d}  [{status}]")

    fk_checks = {
        "Orders.PeopleID -> People":       'SELECT COUNT(*) FROM "Orders" WHERE "PeopleID" NOT IN (SELECT "PeopleID" FROM "People")',
        "Orders.CustomerID -> Customers":  'SELECT COUNT(*) FROM "Orders" WHERE "CustomerID" NOT IN (SELECT "CustomerID" FROM "Customers")',
        "Orders.ShipID -> typeShip":       'SELECT COUNT(*) FROM "Orders" WHERE "ShipID" NOT IN (SELECT "ShipID" FROM "typeShip")',
        "Orders.AddressesID -> Addresses": 'SELECT COUNT(*) FROM "Orders" WHERE "AddressesID" NOT IN (SELECT "AddressesID" FROM "Addresses")',
        "OrderDetails.OrderID -> Orders":  'SELECT COUNT(*) FROM "OrderDetails" WHERE "OrderID" NOT IN (SELECT "OrderID" FROM "Orders")',
        "OrderDetails.ProductCode -> Product": 'SELECT COUNT(*) FROM "OrderDetails" WHERE "ProductCode" NOT IN (SELECT "ProductCode" FROM "Product")',
        "Returns.DetailID -> OrderDetails": 'SELECT COUNT(*) FROM "Returns" WHERE "DetailID" NOT IN (SELECT "DetailID" FROM "OrderDetails")',
        "dateShip.OrderID -> Orders":      'SELECT COUNT(*) FROM "dateShip" WHERE "OrderID" NOT IN (SELECT "OrderID" FROM "Orders")',
    }
    log("")
    for name, q in fk_checks.items():
        orphans = conn.execute(text(q)).scalar()
        status = "OK" if orphans == 0 else "ОШИБКА"
        if orphans != 0:
            all_ok = False
        log(f"  {name:35s} orphan-строк={orphans}  [{status}]")

    total_sales, total_profit = conn.execute(
        text('SELECT SUM("Sales"), SUM("Profit") FROM "OrderDetails"')
    ).one()
    total_sales, total_profit = float(total_sales), float(total_profit)
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
        return 1

    log(f"🔌 Подключаюсь к PostgreSQL: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}")
    engine = create_engine(DB_URL)

    load_raw_into_staging(engine)  # pandas.to_sql сам открывает/закрывает соединения

    with engine.begin() as conn:  # одна транзакция на всё; при ошибке — полный rollback
        build_schema(conn)
        populate_tables(conn)
        cleanup_staging(conn)
        ok = validate(conn)

    engine.dispose()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
