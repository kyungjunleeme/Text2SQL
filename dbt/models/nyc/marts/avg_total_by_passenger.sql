{{ config(materialized='view') }}

select
  passenger_count,
  avg(total_amount) as avg_total
from {{ ref('stg_trips_small') }}
group by 1
order by 2 desc
