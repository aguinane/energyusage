# API Documentation

The following HTTP headers need to be set to authenticate the service request.
> `X-apikey`

> `X-meterid`


## GET /api/v1.0/data-range

```
curl -X GET http://localhost:5000/api/v1.0/data-range -i -H "X-meterid: 1"
```

## POST /api/v1.0/interval-upload

Upload meter readings.

Parameter   | Field     | Format    | Unit  | Example
---         | ---       | ---       | ---   | ---
date        | Date      | YYYYMMDD  |       | 20170120
time        | Time      | hh:mm     |       | 13:01
interval    | Interval  | number       | min   | 10
e1          | Import (Consumption)  | number | Wh | 19
e2          | Import 2 (Controlled Load Consumption) | number | Wh | 0
b1          | Export (Generation) | number | Wh | 1
v           | Voltage | number | V | 240.1
t           | Temperature | number | °C | 24.1

> The date and time is the time at which the interval reading ended.

> The following are allowed interval periods: 1, 5, 10, 15, or 30.

Example

```
curl -X POST http://localhost:5000/api/v1.0/interval-upload -i -H "X-meterid: 1" -H "X-apikey: 0ce839b7-d514-4791-ae40-7eb6f21736c7" -H "Content-type: application/json" -d '[{"date":"20170120", "time":"13:00", "interval":"10", "e1":"19"}]'
```