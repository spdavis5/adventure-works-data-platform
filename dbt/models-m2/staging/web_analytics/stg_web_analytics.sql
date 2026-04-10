with source as (

    select * from {{ source('web_analytics', 'web_analytics_raw') }}

),

renamed as (

    select
        -- Casting to ensure type consistency across the warehouse
        cast(customer_id as int) as customer_id,
        cast(product_id as int) as product_id,
        cast(session_id as varchar) as session_id,
        cast(page_url as varchar) as page_url,
        cast(event_type as varchar) as event_type,
        
        -- Normalizing to UTC and ensuring TIMESTAMP_NTZ for Snowflake
        cast(event_timestamp as timestamp_ntz) as event_timestamp,
        
        -- Metadata for tracking when dbt processed this record
        current_timestamp() as dbt_updated_at

    from source

)

select * from renamed