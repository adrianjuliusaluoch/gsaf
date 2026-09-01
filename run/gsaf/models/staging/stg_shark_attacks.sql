

  create or replace view `data-storage-485106`.`sharks`.`stg_shark_attacks`
  OPTIONS()
  as -- The month's table name is resolved outside dbt entirely -- CI computes
-- it in bash (see "Set dynamic BigQuery table name" step in the workflow)
-- and passes it in as DBT_SHARK_TABLE. This model just reads whatever
-- table name it's handed, so dbt never needs to know the name rotates
-- monthly -- that complexity stays out of the dbt layer completely.
select *
from `data-storage-485106.sharks.attacks_2026_sep`;

