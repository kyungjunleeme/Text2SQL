{{ config(materialized='view') }}
{% set src = var('employees_source', 'employees') %}
select * from {{ src }}
