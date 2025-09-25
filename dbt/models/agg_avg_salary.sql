{{ config(materialized='table') }}

with e as (
  select * from {{ ref('stg_employees') }}
),
d as (
  select * from {{ ref('stg_departments') }}
)
select
  d.name as dept,
  avg(e.salary) as avg_salary
from e
join d on e.dept_id = d.id
group by d.name
order by avg_salary desc
