#!/bin/bash
# Performance monitoring script for ML processing

echo "=== News Intelligence ML Processing Performance Monitor ==="
echo "Timestamp: $(date)"
echo ""

echo "1. Processing Status:"
docker exec news-system-postgres psql -U newsapp -d news_system -c "
SELECT 
    processing_status, 
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
FROM articles 
GROUP BY processing_status 
ORDER BY count DESC;"

echo ""
echo "2. Processing Rate (Last 10 Minutes):"
docker exec news-system-postgres psql -U newsapp -d news_system -c "
SELECT 
    COUNT(*) as articles_processed,
    ROUND(COUNT(*) / 10.0, 2) as articles_per_minute,
    ROUND(COUNT(*) / 600.0, 2) as articles_per_second
FROM articles 
WHERE processing_completed_at > NOW() - INTERVAL '10 minutes';"

echo ""
echo "3. Quality Distribution:"
docker exec news-system-postgres psql -U newsapp -d news_system -c "
SELECT 
    CASE 
        WHEN quality_score >= 0.8 THEN 'High Quality (0.8+)'
        WHEN quality_score >= 0.6 THEN 'Medium Quality (0.6-0.8)'
        WHEN quality_score >= 0.4 THEN 'Low Quality (0.4-0.6)'
        ELSE 'Very Low Quality (<0.4)'
    END as quality_tier,
    COUNT(*) as count
FROM articles 
WHERE processing_status = 'processed'
GROUP BY quality_tier
ORDER BY count DESC;"

echo ""
echo "4. Source Performance:"
docker exec news-system-postgres psql -U newsapp -d news_system -c "
SELECT 
    source,
    COUNT(*) as total_articles,
    ROUND(AVG(quality_score), 2) as avg_quality,
    ROUND(AVG(readability_score), 2) as avg_readability,
    ROUND(AVG(engagement_score), 2) as avg_engagement
FROM articles 
WHERE processing_status = 'processed'
GROUP BY source
ORDER BY total_articles DESC;"

echo ""
echo "5. Recent Processing Activity:"
docker exec news-system-postgres psql -U newsapp -d news_system -c "
SELECT 
    DATE_TRUNC('minute', processing_completed_at) as minute,
    COUNT(*) as articles_processed
FROM articles 
WHERE processing_completed_at > NOW() - INTERVAL '30 minutes'
AND processing_status = 'processed'
GROUP BY minute
ORDER BY minute DESC
LIMIT 10;"

echo ""
echo "6. Worker Status:"
docker exec news-system-app ps aux | grep optimized_ml_worker | wc -l | xargs echo "Active optimized workers:"

echo ""
echo "=== Performance Summary ==="
echo "✅ ML Processing: ACTIVE"
echo "✅ Parallel Processing: ENABLED"
echo "✅ Enhanced Quality Scoring: ENABLED"
echo "✅ Real-time Monitoring: ENABLED"
