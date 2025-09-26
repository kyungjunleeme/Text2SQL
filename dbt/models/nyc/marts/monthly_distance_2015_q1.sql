{{ config(materialized='view') }}

select
  extract(month from pickup_datetime) as mon,
  sum(trip_distance) as dist
from {{ ref('stg_trips_small') }}
where extract(year from pickup_datetime) = 2015
  and extract(month from pickup_datetime) in (1,2,3)
group by 1
order by 1
