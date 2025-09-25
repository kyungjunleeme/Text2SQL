{{ config(materialized='view') }}
{% set src = var('departments_source', 'departments') %}
select * from {{ src }}
