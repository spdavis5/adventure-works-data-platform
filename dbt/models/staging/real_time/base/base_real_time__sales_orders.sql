with source as (
    select * from {{ source('real_time', 'orders_raw') }}
),

renamed as (
    select
        sales_order_id,
        customer_id,
        account_number,
        -- Convert "NaN" strings to NULL for IDs and numeric fields
        try_to_number(nullif(bill_to_address_id::varchar, 'NaN')) as bill_to_address_id,
        nullif(comment::varchar, 'NaN') as comment,
        nullif(credit_card_approval_code::varchar, 'NaN') as credit_card_approval_code,
        try_to_number(nullif(credit_card_id::varchar, 'NaN')) as credit_card_id,
        try_to_number(nullif(currency_rate_id::varchar, 'NaN')) as currency_rate_id,
        cast(null as string) as delivery_estimate,
        due_date,
        try_to_double(nullif(freight::varchar, 'NaN')) as freight,
        cast(last_modified as timestamp) as modified_date,
        try_to_number(nullif(online_order_flag::varchar, 'NaN')) as online_order_flag,
        order_date,
        cast(null as variant) as order_details,
        nullif(purchase_order_number::varchar, 'NaN') as purchase_order_number,
        try_to_number(nullif(revision_number::varchar, 'NaN')) as revision_number,
        sales_order_number,
        try_to_number(nullif(sales_person_id::varchar, 'NaN')) as sales_person_id,
        ship_date,
        try_to_number(nullif(ship_method_id::varchar, 'NaN')) as ship_method_id,
        try_to_number(nullif(ship_to_address_id::varchar, 'NaN')) as ship_to_address_id,
        try_to_number(nullif(status::varchar, 'NaN')) as status,
        try_to_double(nullif(sub_total::varchar, 'NaN')) as sub_total,
        try_to_double(nullif(tax_amt::varchar, 'NaN')) as tax_amt,
        try_to_number(nullif(territory_id::varchar, 'NaN')) as territory_id,
        try_to_double(nullif(total_due::varchar, 'NaN')) as total_due
    from source
)

select * from renamed