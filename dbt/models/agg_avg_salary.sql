{{ config(materialized='table') }}
with e as (
  {% set esrc = var('employees_source', 'employees') %}
  select * from {{ esrc }}
),
d as (
  {% set dsrc = var('departments_source', 'departments') %}
  select * from {{ dsrc }}
)
select d.name as dept, avg(e.salary) as avg_salary
from e
join d on e.dept_id = d.id
group by d.name
