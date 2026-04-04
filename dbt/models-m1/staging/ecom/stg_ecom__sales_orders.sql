with

-- 1. Get the legacy data with explicit columns
legacy_base as (
    select 
        sales_order_id, customer_id, account_number, bill_to_address_id, 
        comment, credit_card_approval_code, credit_card_id, currency_rate_id, 
        delivery_estimate, due_date, freight, modified_date, online_order_flag, 
        order_date, order_details, purchase_order_number, revision_number, 
        sales_order_number, sales_person_id, ship_date, ship_method_id, 
        ship_to_address_id, status, sub_total, tax_amt, territory_id, total_due
    from {{ ref('base_ecom__sales_orders') }}
),

-- 2. Get your new Postgres data with the exact same column order
real_time_base as (
    select 
        sales_order_id, customer_id, account_number, bill_to_address_id, 
        comment, credit_card_approval_code, credit_card_id, currency_rate_id, 
        delivery_estimate, due_date, freight, modified_date, online_order_flag, 
        order_date, order_details, purchase_order_number, revision_number, 
        sales_order_number, sales_person_id, ship_date, ship_method_id, 
        ship_to_address_id, status, sub_total, tax_amt, territory_id, total_due
    from {{ ref('stg_real_time__sales_orders') }}
),

-- 3. Stack them on top of each other
combined as (
    select * from legacy_base
    union all
    select * from real_time_base
),

ship_methods as (
    select * from {{ ref('ship_method') }}
),

final as (
    select
        c.sales_order_id,
        c.customer_id,
        c.account_number,
        c.bill_to_address_id,
        c.comment,
        c.credit_card_approval_code,
        c.credit_card_id,
        c.currency_rate_id,
        
        -- Logic to handle delivery estimates from legacy data
        case 
            when c.delivery_estimate ilike '%week%' 
                then regexp_substr(c.delivery_estimate, '[0-9]+')::int * 7
            when c.delivery_estimate ilike '%day%' 
                then regexp_substr(c.delivery_estimate, '[0-9]+')::int
            else null  
        end as delivery_estimate_days,

        c.due_date,
        c.freight,
        c.modified_date,
        c.online_order_flag,
        c.order_date,
        c.order_details,
        c.purchase_order_number,
        c.revision_number,
        c.sales_order_number,
        c.sales_person_id,
        c.ship_date,
        s.name as shipping_method,
        c.ship_to_address_id,
        c.status,
        c.sub_total,
        c.tax_amt,
        c.territory_id,
        c.total_due
    from combined c
    left join ship_methods s
        on c.ship_method_id = s.ship_method_id
)

select * from final