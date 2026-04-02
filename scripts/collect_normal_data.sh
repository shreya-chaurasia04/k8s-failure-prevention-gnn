#!/bin/bash
# Automated Normal Scenario Data Collection Script
# Purpose: Collect 1,500 normal scenario snapshots to balance the dataset
# Target: 40-50% normal scenarios (currently only 99/1686 = 5.9%)

set -e

# Configuration
COLLECTION_INTERVAL=45  # seconds between snapshots (recommended: 30-60s)
TARGET_SNAPSHOTS=1500   # number of normal snapshots to collect
COLLECTION_SCRIPT="src/collectors/collect_snapshots.py"
DATA_DIR="data/raw"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Normal Scenario Data Collection${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Target: ${YELLOW}${TARGET_SNAPSHOTS}${NC} normal snapshots"
echo -e "Interval: ${YELLOW}${COLLECTION_INTERVAL}s${NC} between snapshots"
echo -e "Estimated duration: ${YELLOW}$(( TARGET_SNAPSHOTS * COLLECTION_INTERVAL / 3600 ))h $(( (TARGET_SNAPSHOTS * COLLECTION_INTERVAL % 3600) / 60 ))m${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}Running pre-flight checks...${NC}"

# Check if Kubernetes cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}✗ Kubernetes cluster not accessible${NC}"
    echo "Please ensure your cluster is running and kubectl is configured"
    exit 1
fi
echo -e "${GREEN}✓ Kubernetes cluster accessible${NC}"

# Check if Prometheus is running
if ! kubectl get pods -n monitoring -l app=prometheus &> /dev/null; then
    echo -e "${RED}✗ Prometheus not found in monitoring namespace${NC}"
    echo "Please deploy Prometheus first"
    exit 1
fi
echo -e "${GREEN}✓ Prometheus is running${NC}"

# Check if collection script exists
if [ ! -f "$COLLECTION_SCRIPT" ]; then
    echo -e "${RED}✗ Collection script not found: $COLLECTION_SCRIPT${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Collection script found${NC}"

# Check current workload status
echo ""
echo -e "${YELLOW}Checking current cluster state...${NC}"
TOTAL_PODS=$(kubectl get pods --all-namespaces --no-headers | wc -l)
RUNNING_PODS=$(kubectl get pods --all-namespaces --field-selector=status.phase=Running --no-headers | wc -l)
echo "Total pods: $TOTAL_PODS"
echo "Running pods: $RUNNING_PODS"

# Verify no chaos experiments are running
CHAOS_PODS=$(kubectl get pods -n workload -l chaos=true --no-headers 2>/dev/null | wc -l)
if [ "$CHAOS_PODS" -gt 0 ]; then
    echo -e "${RED}✗ Chaos experiments detected! Please clean up before collecting normal data${NC}"
    echo "Run: kubectl delete pods -n workload -l chaos=true"
    exit 1
fi
echo -e "${GREEN}✓ No chaos experiments running${NC}"

# Check CPU and memory usage
echo ""
echo -e "${YELLOW}Current resource utilization:${NC}"
kubectl top nodes 2>/dev/null || echo "Note: metrics-server not available"

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}IMPORTANT: Normal Scenario Criteria${NC}"
echo -e "${YELLOW}========================================${NC}"
echo "Ensure the following conditions are met:"
echo "  • No chaos experiments running"
echo "  • All pods in Running state"
echo "  • CPU usage: 20-60% (moderate load)"
echo "  • Memory usage: stable, no spikes"
echo "  • No pod restarts in last 10 minutes"
echo "  • API server latency < 100ms"
echo ""
read -p "Do these conditions look good? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${RED}Collection cancelled. Please ensure normal conditions first.${NC}"
    exit 1
fi

# Count existing normal snapshots
EXISTING_NORMAL=$(ls -1 $DATA_DIR/snapshot_[0-9]*.json 2>/dev/null | wc -l)
echo ""
echo -e "${GREEN}Existing normal snapshots: $EXISTING_NORMAL${NC}"
echo -e "${GREEN}Will collect: $TARGET_SNAPSHOTS additional snapshots${NC}"

# Create collection log
LOG_FILE="logs/normal_collection_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs
echo "Collection started at $(date)" > "$LOG_FILE"
echo "Target: $TARGET_SNAPSHOTS snapshots" >> "$LOG_FILE"
echo "Interval: ${COLLECTION_INTERVAL}s" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Collection${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Log file: $LOG_FILE"
echo "Press Ctrl+C to stop (progress will be saved)"
echo ""

# Trap Ctrl+C to show summary
trap 'echo ""; echo "Collection interrupted by user"; show_summary; exit 0' INT

show_summary() {
    COLLECTED=$(ls -1 $DATA_DIR/snapshot_[0-9]*.json 2>/dev/null | wc -l)
    NEW_COLLECTED=$((COLLECTED - EXISTING_NORMAL))
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Collection Summary${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Started with: $EXISTING_NORMAL normal snapshots"
    echo "Collected: $NEW_COLLECTED new snapshots"
    echo "Total now: $COLLECTED normal snapshots"
    echo "Target: $TARGET_SNAPSHOTS"
    echo "Progress: $(( NEW_COLLECTED * 100 / TARGET_SNAPSHOTS ))%"
    echo ""
    echo "Log saved to: $LOG_FILE"
}

# Collection loop
COLLECTED=0
START_TIME=$(date +%s)

cd "$(dirname "$0")/.."  # Go to project root

while [ $COLLECTED -lt $TARGET_SNAPSHOTS ]; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    # Run collection script once
    if python3 "$COLLECTION_SCRIPT" 2>&1 | head -1 | tee -a "$LOG_FILE"; then
        COLLECTED=$((COLLECTED + 1))
        
        # Calculate progress
        PROGRESS=$(( COLLECTED * 100 / TARGET_SNAPSHOTS ))
        REMAINING=$((TARGET_SNAPSHOTS - COLLECTED))
        ETA_SECONDS=$((REMAINING * COLLECTION_INTERVAL))
        ETA_HOURS=$((ETA_SECONDS / 3600))
        ETA_MINUTES=$(( (ETA_SECONDS % 3600) / 60 ))
        
        echo -e "${GREEN}Progress: $COLLECTED/$TARGET_SNAPSHOTS ($PROGRESS%)${NC} | ETA: ${ETA_HOURS}h ${ETA_MINUTES}m"
        
        # Periodic health check every 50 snapshots
        if [ $((COLLECTED % 50)) -eq 0 ]; then
            echo ""
            echo -e "${YELLOW}Health check at snapshot $COLLECTED...${NC}"
            RUNNING_NOW=$(kubectl get pods --all-namespaces --field-selector=status.phase=Running --no-headers | wc -l)
            if [ "$RUNNING_NOW" -lt "$RUNNING_PODS" ]; then
                echo -e "${RED}⚠ Warning: Pod count decreased from $RUNNING_PODS to $RUNNING_NOW${NC}"
                echo "Consider investigating before continuing"
            else
                echo -e "${GREEN}✓ Cluster health looks good${NC}"
            fi
            echo ""
        fi
        
        # Wait for next collection
        if [ $COLLECTED -lt $TARGET_SNAPSHOTS ]; then
            sleep $COLLECTION_INTERVAL
        fi
    else
        echo -e "${RED}✗ Collection failed, retrying in 10s...${NC}" | tee -a "$LOG_FILE"
        sleep 10
    fi
done

# Final summary
show_summary

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Collection Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Run conversion: python scripts/convert_json_to_csv.py"
echo "2. Verify class balance in data/processed/metadata.csv"
echo "3. Begin GNN model training"
echo ""

# Made with Bob
