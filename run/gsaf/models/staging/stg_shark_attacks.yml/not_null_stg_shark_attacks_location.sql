
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select location
from `data-storage-485106`.`sharks`.`stg_shark_attacks`
where location is null



  
  
      
    ) dbt_internal_test