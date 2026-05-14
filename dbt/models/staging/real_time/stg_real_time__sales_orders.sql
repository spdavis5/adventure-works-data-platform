with orders as (
    select * from {{ ref('base_real_time__sales_orders') }}
),

details as (
    select * from {{ ref('base_real_time__order_details') }}
),

aggregated_details as (
    select
        sales_order_id,
        ARRAY_AGG(
            OBJECT_CONSTRUCT(
                'SalesOrderDetailID', sales_order_detail_id,
                'OrderQty', order_qty,
                'ProductID', product_id,
                'UnitPrice', unit_price,
                'LineTotal', line_total
            )
        ) as order_details_array
    from details
    group by 1
),

final as (
    select
        o.sales_order_id,
        o.customer_id,
        o.account_number,
        o.bill_to_address_id,
        o.comment,
        o.credit_card_approval_code,
        o.credit_card_id,
        o.currency_rate_id,
        o.delivery_estimate,
        o.due_date,
        o.freight,
        o.modified_date,
        o.online_order_flag,
        o.order_date,
        -- Replacing the NULL placeholder with the actual array
        coalesce(ad.order_details_array, cast([] as variant)) as order_details,
        o.purchase_order_number,
        o.revision_number,
        o.sales_order_number,
        o.sales_person_id,
        o.ship_date,
        o.ship_method_id,
        o.ship_to_address_id,
        o.status,
        o.sub_total,
        o.tax_amt,
        o.territory_id,
        o.total_due
    from orders o
    left join aggregated_details ad
        on o.sales_order_id = ad.sales_order_id
)

select * from final