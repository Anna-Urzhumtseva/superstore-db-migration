CREATE VIEW v_sales_dashboard AS
select 
o.OrderID,
o.OrderDate,
ts.ShipMode,
ds.ShipDate,
p.Person,
p.Region,
c.CustomerName,
c.Segment,
a.City,
a.Country,
a.State,
a.PostalCode,
od.Discount,
od.Profit,
od.Quantity,
od.Sales,
r.Returned,
p.Person,
p.Region 
from Orders o 
left join typeShip ts on o.ShipID  = ts.ShipID 
left join dateShip ds on ds.OrderID  = o.OrderID  
left join People p on p.PeopleID = o.PeopleID 
left join Customers c  on c.CustomerID = o.CustomerID 
left join Addresses a on a.AddressesID = o.AddressesID 
left join OrderDetails od on od.OrderID = o.OrderID
left join "Returns" r on r.DetailID = od.DetailID 
left join Product p2 on p2.ProductCode = od.ProductCode ;

SELECT * FROM v_sales_dashboard LIMIT 10;