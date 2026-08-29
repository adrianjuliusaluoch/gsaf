
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select date
from `data-storage-485106`.`sharks`.`stg_shark_attacks`
where date is null



  
  
      
    ) dbt_internal_test