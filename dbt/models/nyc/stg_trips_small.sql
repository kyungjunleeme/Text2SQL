{{ config(materialized='view') }}

-- 원본에 빈 문자열/타입 섞임 → DuckDB TRY_CAST로 안전 캐스팅
select
  try_cast(pickup_datetime as timestamp)  as pickup_datetime,
  try_cast(dropoff_datetime as timestamp) as dropoff_datetime,
  try_cast(passenger_count as int)        as passenger_count,
  try_cast(trip_distance as double)       as trip_distance,
  try_cast(total_amount as double)        as total_amount,
  pickup_ntaname,
  dropoff_ntaname,
  payment_type
from {{ source('nyc','trips_small') }}
