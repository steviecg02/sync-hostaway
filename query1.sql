WITH metric_data AS
    (SELECT metric_date,
            TO_CHAR(metric_date, 'Dy') AS day_of_week,
            conversion_rate_your_value,
            conversion_rate_similar_value,
            p3_impressions_your_value,
            p3_impressions_similar_value
     FROM airbnb_chart_query
     WHERE TIME = '2025-07-08 22:41:04.049679+00'
         AND airbnb_listing_id = '745515258634591476'),
     res_data AS
    (SELECT reservation_id,
            check_in_date,
            check_out_date,
            check_in_date::date - reservation_date::date AS booking_window,
            pms_meta->>'channelName' AS channel,
            listing_id
     FROM reservations
     WHERE listing_id =
             (SELECT listing_id
              FROM listings
              WHERE pms_meta->>'airbnbListingUrl' LIKE '%745515258634591476')
         AND status IN ('new',
                        'modified')
         AND ((check_in_date <= CURRENT_DATE
               AND check_out_date >= CURRENT_DATE - INTERVAL '180 days')
              OR (check_in_date <= CURRENT_DATE + INTERVAL '180 days'
                  AND check_out_date >= CURRENT_DATE)))
SELECT m.metric_date,
       m.day_of_week,
       r.reservation_id,
       r.booking_window,
       r.channel,
       m.p3_impressions_your_value,
       m.p3_impressions_similar_value,
       m.conversion_rate_your_value,
       m.conversion_rate_similar_value
FROM metric_data m
LEFT JOIN res_data r ON m.metric_date >= r.check_in_date
AND m.metric_date < r.check_out_date
ORDER BY m.metric_date;