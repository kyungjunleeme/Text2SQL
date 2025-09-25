{{ config(materialized='view') }}

select
  id,
  name
from {{ ref('departments') }}
