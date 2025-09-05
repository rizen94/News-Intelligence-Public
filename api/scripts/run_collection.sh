#!/bin/bash
# Run automated collection inside Docker container

echo "Starting automated RSS collection and ML processing..."

# Run the collection script inside the news-system-app container
docker exec news-system-app python3 /app/scripts/automated_collection.py

echo "Collection completed."
