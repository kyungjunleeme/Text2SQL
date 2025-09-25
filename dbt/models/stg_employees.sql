{{ config(materialized='view') }}

select
  id,
  name,
  dept_id,
  salary
from {{ ref('employees') }}
