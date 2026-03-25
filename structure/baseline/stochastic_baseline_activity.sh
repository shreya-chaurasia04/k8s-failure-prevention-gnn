#!/bin/bash
# Check if port-forward is running - simulating running frontend locally on port 8080
if ! nc -z localhost 8080; then
    echo "❌ Error: Port 8080 is not open. Run 'kubectl port-forward svc/frontend-svc -n workload 8080:80' in another terminal first."
    exit 1
fi

echo "🚀 Starting Stochastic Baseline (Normal Operations)..."

MIN_REQ=10
MAX_REQ=50 

for i in {1..10}; do
  REQ_COUNT=$(( ( RANDOM % (MAX_REQ - MIN_REQ + 1 ) ) + MIN_REQ ))
  echo "--- Batch $i: Sending $REQ_COUNT heartbeat requests to Frontend ---"
  
  for j in $(seq 1 $REQ_COUNT); do
    curl -s http://localhost:8080 > /dev/null &
  done
  
  # Wait for background curls to finish
  wait
  sleep 10
done

echo "✅ Baseline data generation complete."