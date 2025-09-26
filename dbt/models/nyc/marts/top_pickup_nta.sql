{{ config(materialized='view') }}

select
  pickup_ntaname,
  count(*) as cnt
from {{ ref('stg_trips_small') }}
where pickup_ntaname is not null and pickup_ntaname <> ''
group by 1
order by 2 desc
limit 10
