WITH t1 AS (
    SELECT DISTINCT 
        "Product ID" AS ProductID,
        Category,
        "Sub-Category" AS SubCategory,
        "Product Name" AS ProductName
    FROM Orders
), 
newProduct AS (
    SELECT 
        ProductID,
        Category,
        SubCategory,
        ProductName,
        ROW_NUMBER() OVER (ORDER BY ProductID) AS ProductCode
    FROM t1
),
t2 AS (
    SELECT DISTINCT 
        "Country/Region" AS Country,
        City,
        State,
        "Postal Code" AS PostalCode,
        "Customer ID" AS CustomerID
    FROM Orders
),
newAddresses AS (
    SELECT DISTINCT
        Country,
        City,
        State,
        PostalCode,
        CustomerID,
        ROW_NUMBER() OVER (ORDER BY CustomerID, Country, City, State, PostalCode) AS AddressesID
    FROM t2
),
t3 AS (
    SELECT DISTINCT 
        "Ship Mode" AS ShipMode
    FROM Orders
),
newTypeShip AS (
    SELECT DISTINCT
        ROW_NUMBER() OVER (ORDER BY ShipMode) AS ShipID,    
        ShipMode    
    FROM t3
),
t5 AS (
    SELECT person, region
    FROM People
),
newPeople AS (
    SELECT DISTINCT
        person,
        region,
        ROW_NUMBER() OVER (ORDER BY person, region) AS PeopleID
    FROM t5
),
newCustomers AS (
    SELECT DISTINCT
        o."Customer ID" AS CustomerID,
        o."Customer Name" AS CustomerName,
        o.Segment 
    FROM Orders o 
),
t4 AS (
    SELECT DISTINCT 
        "Order ID" AS OrderID,
        "Order Date" AS OrderDate,
        COALESCE(Region, '-') AS Region,
        COALESCE("Customer ID", '-') AS CustomerID,
        COALESCE("Ship Mode", '-') AS ShipMode   
    FROM Orders
),
newOrders AS (
    SELECT DISTINCT
        t4.OrderID,
        t4.OrderDate,
        ts.ShipID,
        p.PeopleID,
        t4.CustomerID
    FROM t4
    LEFT JOIN newPeople p ON p.region = t4.Region 
    LEFT JOIN newTypeShip ts ON ts.ShipMode = t4.ShipMode
),
t6 AS (
    SELECT DISTINCT 
        "Order ID" AS OrderID,
        COALESCE(p.ProductCode, '-') AS ProductCode, 
        Quantity,
        Sales,
        Discount,
        Profit
    FROM Orders o
    LEFT JOIN newProduct p ON p.ProductID = o."Product ID" AND p.ProductName = o."Product Name" 
    order by "Order ID",ProductCode,Quantity,Sales,Discount,Profit
),
newOrderDetails AS (
    SELECT DISTINCT
        OrderID, 
        ProductCode, 
        Quantity,
        Sales,
        Discount,
        Profit,
        ROW_NUMBER() OVER (ORDER BY OrderID,ProductCode,Quantity,Sales,Discount,Profit) AS DetailID
    FROM t6
),
t7 as (
	SELECT DISTINCT
	    "Order ID" AS OrderID,
	    "Ship Date" AS ShipDate,
	    ts.ShipID 
	FROM Orders o
	left join newTypeShip ts on ts.ShipMode = o."Ship Mode" 
	order by "Order ID", "Ship Date",ts.ShipID 
),
newDateShip as (
	SELECT DISTINCT
		ShipID,OrderID,ShipDate,
		ROW_NUMBER() OVER (ORDER BY OrderID,ShipDate,ShipID) AS dateShipID
	FROM t7
	order by  OrderID,ShipDate,ShipID
),
t8 as(
select DISTINCT  r.returned, od.DetailID 
from returns r
LEFT JOIN newOrderDetails  od ON od.OrderID = r."Order ID"
ORDER by  od.DetailID ,r.returned
),
newReturns as(
SELECT returned,DetailID,
ROW_NUMBER() OVER (ORDER BY DetailID,returned) AS ReturnID
FROM t8  
ORDER by  DetailID,returned
)
select * from newReturns 