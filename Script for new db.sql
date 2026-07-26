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
        ifnull("Postal Code", 00000.0) AS PostalCode
    FROM Orders
    ORDER BY "Country/Region", State, City, "Postal Code"
),
newAddresses AS (
    SELECT DISTINCT
        Country,
        City,
        State,
        PostalCode,
        ROW_NUMBER() OVER (ORDER BY Country, City, State, PostalCode) AS AddressesID
    FROM t2
    ORDER BY Country, City, State, PostalCode
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
t41 AS (
    SELECT DISTINCT 
        o."Order ID" AS OrderID,
        o."Order Date" AS OrderDate,
        ifnull(o.Region, '-') AS Region,
        o."Customer ID" AS CustomerID,
        o."Ship Mode" AS ShipMode,  
        o."Country/Region" AS Country,
        o.City,
        o.State,                               -- ← исправлено: добавлена запятая
        ifnull(o."Postal Code", 00000.0) AS PostalCode 
    FROM Orders o
),
t42 AS (
    SELECT DISTINCT 
        t41.OrderID,
        t41.OrderDate,
        t41.Region,                            -- ← исправлено: вместо ifnull(o.Region, '-')
        t41.CustomerID,
        t41.ShipMode,  
        a.AddressesID
    FROM t41
    LEFT JOIN newAddresses a ON a.City = t41.City 
                             AND a.Country = t41.Country 
                             AND a.State = t41.State 
                             AND a.PostalCode = t41.PostalCode  
),
newOrders AS (
    SELECT DISTINCT
        t42.OrderID,
        t42.OrderDate,
        ts.ShipID,
        p.PeopleID,
        t42.CustomerID,
        t42.AddressesID
    FROM t42
    LEFT JOIN newPeople p ON p.region = t42.Region          -- ← исправлено: t42 вместо t4
    LEFT JOIN newTypeShip ts ON ts.ShipMode = t42.ShipMode  -- ← исправлено: t42 вместо t4
    ORDER BY t42.OrderDate, t42.CustomerID, t42.OrderID
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
    ORDER BY "Order ID", ProductCode, Quantity, Sales, Discount, Profit
),
newOrderDetails AS (
    SELECT DISTINCT
        OrderID, 
        ProductCode, 
        Quantity,
        Sales,
        Discount,
        Profit,
        ROW_NUMBER() OVER (ORDER BY OrderID, ProductCode, Quantity, Sales, Discount, Profit) AS DetailID
    FROM t6
),
t7 AS (
    SELECT DISTINCT
        "Order ID" AS OrderID,
        "Ship Date" AS ShipDate,
        ts.ShipID 
    FROM Orders o
    LEFT JOIN newTypeShip ts ON ts.ShipMode = o."Ship Mode" 
    ORDER BY "Order ID", "Ship Date", ts.ShipID 
),
newDateShip AS (
    SELECT DISTINCT
        ShipID,
        OrderID,
        ShipDate,
        ROW_NUMBER() OVER (ORDER BY OrderID, ShipDate, ShipID) AS dateShipID
    FROM t7
    ORDER BY OrderID, ShipDate, ShipID
),
t8 AS (
    SELECT DISTINCT r.returned, od.DetailID 
    FROM returns r
    LEFT JOIN newOrderDetails od ON od.OrderID = r."Order ID"
    ORDER BY od.DetailID, r.returned
),
newReturns AS (
    SELECT returned, DetailID,
        ROW_NUMBER() OVER (ORDER BY DetailID, returned) AS ReturnID
    FROM t8  
    ORDER BY DetailID, returned
)
SELECT * FROM newOrders ;   