#!/bin/bash
echo "Building React app with Docker..."

# Build the React app using Docker
docker run --rm -v "$(pwd)/web:/app" -w /app node:18-alpine sh -c "
  npm install --legacy-peer-deps && 
  npm run build
"

echo "React build completed!"
