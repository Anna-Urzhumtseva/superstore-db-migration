CREATE VIEW v_sales_dashboard AS
SELECT 
    od.DetailID,
    od.OrderID,
    od.ProductCode,
    od.Quantity,
    od.Sales,
    od.Discount,
    od.Profit,
    o.OrderDate,
    ds.ShipDate,
    ts.ShipMode,
    c.CustomerID,
    c.CustomerName,
    c.Segment,
    a.Country,
    a.City,
    a.State,
    a.PostalCode,
    p.ProductID AS ProductCodeText,  -- текстовый код, если понадобится
    p.Category,
    p.SubCategory,
    p.ProductName,
    pe.Person AS Manager,
    pe.Region,
    r.Returned,
    r.ReturnID
FROM OrderDetails od
LEFT JOIN Orders o ON od.OrderID = o.OrderID
LEFT JOIN Customers c ON o.CustomerID = c.CustomerID
LEFT JOIN Addresses a ON c.CustomerID = a.CustomerID
LEFT JOIN Product p ON od.ProductCode = p.ProductCode
LEFT JOIN People pe ON o.PeopleID = pe.PeopleID
LEFT JOIN typeShip ts ON o.ShipID = ts.ShipID
LEFT JOIN dateShip ds ON o.OrderID = ds.OrderID AND o.ShipID = ds.ShipID
LEFT JOIN Returns r ON od.DetailID = r.DetailID;

SELECT * FROM v_sales_dashboard LIMIT 10;