with orders as (
    select * from {{ ref('stg_ecom__sales_orders') }}
),

customers as (
    select * from {{ ref('stg_adventure_db__customers') }}
),

final as (
    select
        o.*,
        c.first_name || ' ' || c.last_name as customer_name,
        c.email_address,
        c.country_region as country
    from orders o
    left join customers c
        on o.customer_id = c.customer_id
)

select * from final