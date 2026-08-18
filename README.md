# 🗃️ Миграция и нормализация данных Superstore

Проект по переносу данных из плоской Excel-таблицы (9 994 записи) в нормализованную реляционную базу данных.
Демонстрирует навыки **ETL**, **проектирования БД**, **SQL** и **Python**.

Пайплайн реализован для двух СУБД на выбор — **SQLite** и **PostgreSQL** — с одинаковой логикой трансформации и одинаковым набором автоматических проверок.

---

## 📌 Цель

- Устранить дублирование и избыточность данных.
- Спроектировать нормализованную структуру (3-я нормальная форма).
- Реализовать полностью автоматический ETL-пайплайн для загрузки данных.
- Получить готовую базу для аналитики и BI.

---

## 🧩 Структура базы данных

База состоит из 9 таблиц с внешними ключами:

| Таблица | Описание | Количество записей |
|---------|----------|-------------------|
| `Product` | Справочник товаров | 1 894 |
| `Customers` | Клиенты | 793 |
| `People` | Менеджеры | 4 |
| `typeShip` | Способы доставки | 4 |
| `Addresses` | Адреса клиентов | 632 |
| `Orders` | Заказы | 5 009 |
| `OrderDetails` | Позиции заказов | 9 993 |
| `dateShip` | Даты и способы доставки по заказам | 5 009 |
| `Returns` | Возвраты | 800 |

Связи реализованы через внешние ключи (FOREIGN KEY). Схема — см. `docs/erdNewDB.png` (исходник — `docs/erdNewDB.drawio`).

---

## ⚙️ ETL-процесс

Вся трансформация выполняется одним скриптом — без ручного редактирования в Excel, без промежуточных файлов:

1. **Extract** — сырые данные читаются напрямую из `data/raw/Sample_-_Superstore_format.xlsx` (`pandas`) в staging-таблицы внутри новой базы.
2. **Transform** — дедупликация, создание суррогатных ключей (`ProductCode`, `AddressesID`, `ShipID` и др.), разделение на 9 сущностей через `INSERT INTO … SELECT` с `DISTINCT` и `JOIN`.
3. **Load** — staging-таблицы удаляются, в базе остаётся только финальная нормализованная схема.
4. **Validate** — скрипт сам сверяет количество строк по каждой таблице, проверяет отсутствие orphan-записей по всем FK и сравнивает `SUM(Sales)`/`SUM(Profit)` с контрольной суммой из исходного файла.

### Вариант 1 — SQLite

```bash
cd src
python build_new_db.py
```

Создаёт `data/sqlite/newdatabase.db`.

### Вариант 2 — PostgreSQL

```bash
pip install sqlalchemy psycopg2-binary

$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGDATABASE="superstore"
$env:PGUSER="postgres"
$env:PGPASSWORD="ваш_пароль"

cd src
python build_new_db_postgres.py
```

База `superstore` должна быть заранее создана в PostgreSQL (например, через pgAdmin).

Оба скрипта в конце выводят одинаковый отчёт проверки:

```
✅ ПРОВЕРКА РЕЗУЛЬТАТА
  Product         ожидание=  1894  факт=  1894  [OK]
  ...
  SUM(Sales)  ожидание=2,296,919.49  факт=2,296,919.49  [OK]
  SUM(Profit) ожидание=286,409.08  факт=286,409.08  [OK]
🎉 ВСЁ СОШЛОСЬ, база собрана корректно.
```

Дополнительно в `data/sqlite/` есть:
- `struktureDB.sql` — просмотр структуры таблиц (`PRAGMA table_info`)
- `transform_data.sql` — черновой вариант трансформации через CTE (предыдущая версия пайплайна, оставлена для истории)
- `viewdb.sql` — аналитическая вьюха `v_sales_dashboard` и примеры запросов для BI

---

## 🛠️ Инструменты

- **Python** — `pandas`, `sqlite3`, `sqlalchemy`, `psycopg2`, `openpyxl`
- **SQL** — `CTE`, `ROW_NUMBER()`, `LEFT JOIN`, `INSERT … SELECT`
- **SQLite** и **PostgreSQL** — целевые СУБД
- **DBeaver / pgAdmin** — визуализация схемы и контроль
- **POWER BI** — BI-система
- **VS Code** — среда разработки

---

## 📁 Структура проекта

```
superstore-db-migration/
├── BI/                              # дашборд Power BI
├── data/
│   ├── raw/
│   │   ├── Sample_-_Superstore_format.xlsx
│   │   └── Sample_-_Superstore.xlsx
│   └── sqlite/
│       ├── newdatabase.db          # создаётся build_new_db.py
│       ├── old_database.db         # промежуточная плоская БД (создаётся addDB.py)
│       ├── struktureDB.sql         # просмотр структуры таблиц
│       ├── transform_data.sql      # черновой вариант трансформации через CTE
│       └── viewdb.sql              # аналитическая вьюха и примеры запросов
├── docs/
│   ├── erdNewDB.drawio
│   └── erdNewDB.png
├── src/
│   ├── addDB.py                    # Excel -> old_database.db (плоская БД, SQLite)
│   ├── build_new_db.py             # Excel -> newdatabase.db (нормализованная БД, SQLite)
│   └── build_new_db_postgres.py    # Excel -> superstore (нормализованная БД, PostgreSQL)
├── .gitignore
├── LICENSE
└── README.md
```
