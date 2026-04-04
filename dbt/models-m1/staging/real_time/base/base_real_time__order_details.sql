with source as (
    select * from {{ source('real_time', 'order_details_raw') }}
),

renamed as (
    select
        sales_order_detail_id,
        sales_order_id,
        carrier_tracking_number,
        order_qty,
        product_id,
        special_offer_id,
        -- Force to varchar first so TRY_TO_DOUBLE works
        try_to_double(unit_price::varchar) as unit_price,
        try_to_double(unit_price_discount::varchar) as unit_price_discount,
        try_to_double(line_total::varchar) as line_total,
        last_modified as modified_date
    from source
)

select * from renamed