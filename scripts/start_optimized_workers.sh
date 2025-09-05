#!/bin/bash
# Start optimized ML workers for parallel processing

echo "=== Starting Optimized ML Workers ==="

# Stop any existing ML workers
echo "1. Stopping existing ML workers..."
docker exec news-system-app pkill -f ml_worker.py || echo "No existing workers found"

# Copy optimized worker to container
echo "2. Copying optimized ML worker..."
docker cp /home/pete/Documents/Projects/News\ Intelligence/api/scripts/optimized_ml_worker.py news-system-app:/app/scripts/
docker exec news-system-app chmod +x /app/scripts/optimized_ml_worker.py

# Start multiple optimized workers
echo "3. Starting optimized ML workers..."

# Worker 1: 4 threads, batch size 20
docker exec -d news-system-app python3 /app/scripts/optimized_ml_worker.py --worker-id 1 --max-workers 4 --batch-size 20

# Worker 2: 4 threads, batch size 20  
docker exec -d news-system-app python3 /app/scripts/optimized_ml_worker.py --worker-id 2 --max-workers 4 --batch-size 20

# Worker 3: 4 threads, batch size 20
docker exec -d news-system-app python3 /app/scripts/optimized_ml_worker.py --worker-id 3 --max-workers 4 --batch-size 20

echo "4. Started 3 optimized ML workers with 4 threads each (12 total processing threads)"
echo "5. Each worker processes 20 articles per batch"
echo "6. Total processing capacity: 60 articles per batch cycle"

# Show running workers
echo "7. Running ML workers:"
docker exec news-system-app ps aux | grep optimized_ml_worker || echo "Workers starting up..."

echo "=== Optimized ML Processing Started ==="
echo "Monitor progress with: docker logs news-system-app | grep 'Worker'"
