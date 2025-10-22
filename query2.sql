WITH annotated AS (
    SELECT 
        metric_date,
        time::date AS poll_date,
        metric_date - time::date AS lookback,

        -- Current + Previous values
        conversion_rate_your_value,
        LAG(conversion_rate_your_value) OVER (PARTITION BY metric_date ORDER BY time::date) AS prev_conversion_rate_your_value,

        conversion_rate_similar_value,
        LAG(conversion_rate_similar_value) OVER (PARTITION BY metric_date ORDER BY time::date) AS prev_conversion_rate_similar_value,

        p3_impressions_your_value,
        LAG(p3_impressions_your_value) OVER (PARTITION BY metric_date ORDER BY time::date) AS prev_p3_impressions_your_value,

        p3_impressions_similar_value,
        LAG(p3_impressions_similar_value) OVER (PARTITION BY metric_date ORDER BY time::date) AS prev_p3_impressions_similar_value
    FROM airbnb_chart_query
    WHERE airbnb_listing_id = '745515258634591476'
    AND metric_date <= time::date
),
changes AS (
    SELECT *,
        CASE
            WHEN prev_conversion_rate_your_value IS NULL THEN NULL
            WHEN conversion_rate_your_value IS DISTINCT FROM prev_conversion_rate_your_value THEN TRUE
            ELSE FALSE
        END AS has_changed_conversion_rate_your_value,

        CASE
            WHEN prev_conversion_rate_similar_value IS NULL THEN NULL
            WHEN conversion_rate_similar_value IS DISTINCT FROM prev_conversion_rate_similar_value THEN TRUE
            ELSE FALSE
        END AS has_changed_conversion_rate_similar_value,

        CASE
            WHEN prev_p3_impressions_your_value IS NULL THEN NULL
            WHEN p3_impressions_your_value IS DISTINCT FROM prev_p3_impressions_your_value THEN TRUE
            ELSE FALSE
        END AS has_changed_p3_impressions_your_value,

        CASE
            WHEN prev_p3_impressions_similar_value IS NULL THEN NULL
            WHEN p3_impressions_similar_value IS DISTINCT FROM prev_p3_impressions_similar_value THEN TRUE
            ELSE FALSE
        END AS has_changed_p3_impressions_similar_value
    FROM annotated
)
SELECT *
FROM changes
WHERE lookback = -14 AND (
    has_changed_conversion_rate_your_value = TRUE OR
    has_changed_conversion_rate_similar_value = TRUE OR
    has_changed_p3_impressions_your_value = TRUE OR
    has_changed_p3_impressions_similar_value = TRUE
)
ORDER BY metric_date;