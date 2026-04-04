with source as (
    select * from {{ source('real_time', 'chat_logs_raw') }}
),

flattened as (
    select
        raw:"_id"::string as chat_id,
        raw:"customer_id"::string as customer_id,
        -- Using the correct keys found in your raw data
        raw:"chat_start_time"::timestamp as session_start,
        raw:"chat_completion_time"::timestamp as session_end,
        raw:"ticket_description"::string as ticket_description,
        raw:"customer_satisfaction_rating"::int as rating,
        raw:"last_modified"::timestamp as last_modified
    from source
)

select * from flattened