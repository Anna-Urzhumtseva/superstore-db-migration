import pandas as pd
import sqlite3
from pathlib import Path

# Пути к файлам
BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILE = BASE_DIR / "data" / "sqlite" / "newdatabase.db"
EXCEL_FILE = BASE_DIR / "data" / "raw" / "Sample_-_Superstore MODIFICATED.xlsx"

# Подключаемся к базе
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

cursor.executescript('''
    DROP TABLE IF EXISTS Returns;
    DROP TABLE IF EXISTS OrderDetails;
    DROP TABLE IF EXISTS dateShip;
    DROP TABLE IF EXISTS Orders;
    DROP TABLE IF EXISTS Product;
    DROP TABLE IF EXISTS Addresses;
    DROP TABLE IF EXISTS Customers;
    DROP TABLE IF EXISTS People;
    DROP TABLE IF EXISTS typeShip;
''')

cursor.executescript('''
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
        Returned INTEGER,
        DetailID INTEGER,
        FOREIGN KEY (DetailID) REFERENCES OrderDetails(DetailID)
    );
''')

print("✅ Таблицы созданы!")

file_path = EXCEL_FILE

def rename_columns(df, mapping):
    for old, new in mapping.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)
    return df

try:
    df_product = pd.read_excel(file_path, sheet_name='Product')
    df_product.to_sql('Product', conn, if_exists='append', index=False)
    print(f"✅ Product: {len(df_product)} записей")

    df_people = pd.read_excel(file_path, sheet_name='People')
    df_people.to_sql('People', conn, if_exists='append', index=False)
    print(f"✅ People: {len(df_people)} записей")

    df_customers = pd.read_excel(file_path, sheet_name='Customers')
    rename_columns(df_customers, {'Customer ID': 'CustomerID', 'Customer Name': 'CustomerName'})
    df_customers.to_sql('Customers', conn, if_exists='append', index=False)
    print(f"✅ Customers: {len(df_customers)} записей")

    df_typeship = pd.read_excel(file_path, sheet_name='typeShip')
    rename_columns(df_typeship, {'Ship Mode': 'ShipMode'})
    df_typeship.to_sql('typeShip', conn, if_exists='append', index=False)
    print(f"✅ typeShip: {len(df_typeship)} записей")

    df_addresses = pd.read_excel(file_path, sheet_name='Addresses')
    rename_columns(df_addresses, {'Postal Code': 'PostalCode'})  # убираем CustomerID, его нет
    df_addresses.to_sql('Addresses', conn, if_exists='append', index=False)
    print(f"✅ Addresses: {len(df_addresses)} записей")

    # Загрузка Orders с проверкой наличия столбца AddressesID
    df_orders = pd.read_excel(file_path, sheet_name='Orders')
    rename_columns(df_orders, {
        'Order ID': 'OrderID',
        'Order Date': 'OrderDate',
        'Ship ID': 'ShipID',
        'People ID': 'PeopleID',
        'Customer ID': 'CustomerID',
        'Addresses ID': 'AddressesID'  # если столбца нет, rename пропустит
    })
    
    # Если столбца AddressesID нет в данных, создаём его с NULL (можно заполнить позже)
    if 'AddressesID' not in df_orders.columns:
        df_orders['AddressesID'] = None
        print("⚠️ В листе Orders нет столбца 'Addresses ID', добавлен NULL-столбец.")
        print("   Чтобы заполнить, запустите ETL-скрипт для создания связей.")
    
    df_orders.to_sql('Orders', conn, if_exists='append', index=False)
    print(f"✅ Orders: {len(df_orders)} записей")

    df_dateship = pd.read_excel(file_path, sheet_name='dateShip')
    rename_columns(df_dateship, {'Order ID': 'OrderID', 'Ship Date': 'ShipDate', 'Ship ID': 'ShipID'})
    df_dateship.to_sql('dateShip', conn, if_exists='append', index=False)
    print(f"✅ dateShip: {len(df_dateship)} записей")

    df_orderDetails = pd.read_excel(file_path, sheet_name='OrderDetails')
    rename_columns(df_orderDetails, {'Order ID': 'OrderID', 'Product Code': 'ProductCode'})
    df_orderDetails.to_sql('OrderDetails', conn, if_exists='append', index=False)
    print(f"✅ OrderDetails: {len(df_orderDetails)} записей")

    df_returns = pd.read_excel(file_path, sheet_name='Returns')
    rename_columns(df_returns, {'Detail ID': 'DetailID'})
    df_returns.to_sql('Returns', conn, if_exists='append', index=False)
    print(f"✅ Returns: {len(df_returns)} записей")

except FileNotFoundError:
    print("❌ Файл не найден!")
except Exception as e:
    print(f"❌ Ошибка: {e}")

conn.commit()
conn.close()
print("✅ База данных успешно создана и заполнена!")