with clickstream as (

    select * from {{ ref('stg_web_analytics') }}

),

customers as (

    select * from {{ ref('stg_adventure_db__customers') }}

),

enriched as (

    select
        -- Clickstream attributes
        s.session_id,
        s.page_url,
        s.event_type,
        s.event_timestamp,
        
        -- Customer identifiers
        s.customer_id,
        c.full_name,
        c.email_address,
        
        -- Geography for regional analysis
        c.city,
        c.state_province,
        c.country_region,
        c.postal_code

    from clickstream s
    left join customers c
        on cast(s.customer_id as string) = c.customer_id

)

select * from enriched