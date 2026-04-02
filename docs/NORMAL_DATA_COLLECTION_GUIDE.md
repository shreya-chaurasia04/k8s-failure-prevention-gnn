# Normal Data Collection Guide

## Overview

This guide provides instructions for collecting additional normal scenario data to balance your dataset for GNN training.

**Current Status**: 99 normal / 1,587 stress = 5.9% normal (SEVERELY IMBALANCED)  
**Target**: 1,500 normal snapshots to achieve 40-50% balance  
**Collection Time**: ~18-21 hours at 45s intervals

---

## Why This Matters

### Current Problem
- **94% stress scenarios** → Model will be biased toward predicting failures
- **High false positive rate** → System will cry wolf too often
- **Poor generalization** → Won't recognize actual normal operations

### Target Balance
- **40-50% normal scenarios** → Balanced learning
- **50-60% stress scenarios** → Adequate failure pattern recognition
- **Better model performance** → Accurate predictions in production

---

## Collection Methods

### Method 1: Automated Shell Script (Recommended for Long Runs)

**Best for**: Overnight/multi-day collection

```bash
# Make executable
chmod +x scripts/collect_normal_data.sh

# Run collection
./scripts/collect_normal_data.sh
```

**Features**:
- Pre-flight checks (cluster health, Prometheus status)
- Automatic health monitoring every 50 snapshots
- Progress tracking with ETA
- Graceful interruption (Ctrl+C saves progress)
- Detailed logging

**Output**: JSON files in `data/raw/snapshot_*.json`

---

### Method 2: Direct CSV Collection (Recommended for Efficiency)

**Best for**: Direct integration with training pipeline

```bash
# Run Python script
python3 scripts/collect_normal_data_csv.py
```

**Features**:
- Writes directly to CSV (no conversion needed)
- Separate files for normal data
- Append mode (can resume if interrupted)
- Real-time progress tracking

**Output**: CSV files in `data/processed/`:
- `node_features_normal.csv`
- `edge_features_normal.csv`
- `graph_features_normal.csv`
- `metadata_normal.csv`

---

### Method 3: Manual Collection (For Testing)

**Best for**: Short collection sessions, testing

```bash
cd src/collectors
python3 collect_snapshots.py
```

Press Ctrl+C to stop. Collects every 30 seconds.

---

## Pre-Collection Checklist

### ✅ Cluster Requirements

1. **Kubernetes cluster running**
   ```bash
   kubectl cluster-info
   ```

2. **Prometheus deployed and accessible**
   ```bash
   kubectl get pods -n monitoring -l app=prometheus
   ```

3. **No chaos experiments active**
   ```bash
   kubectl get pods -n workload -l chaos=true
   # Should return: No resources found
   ```

4. **All pods in Running state**
   ```bash
   kubectl get pods --all-namespaces
   ```

### ✅ Normal Scenario Criteria

Ensure these conditions are met:

| Criterion | Target | Check Command |
|-----------|--------|---------------|
| CPU Usage | 20-60% | `kubectl top nodes` |
| Memory Usage | Stable, no spikes | `kubectl top nodes` |
| Pod Restarts | 0 in last 10 min | `kubectl get pods --all-namespaces` |
| API Latency | < 100ms | Check Prometheus |
| Pod Status | All Running | `kubectl get pods --all-namespaces` |
| Failed Pods | 0 | `kubectl get pods --field-selector=status.phase=Failed` |

### ✅ Workload Recommendations

**Ideal normal workload**:
- Moderate traffic (not idle, not stressed)
- Consistent request patterns
- No deployments or updates during collection
- Stable resource utilization

**Generate moderate load** (optional):
```bash
# Deploy workload generator with moderate settings
kubectl apply -f k8s-manifests/workload-generator.yaml
```

---

## Collection Strategies

### Strategy 1: Continuous Collection (Recommended)

**Duration**: 18-21 hours  
**Interval**: 45 seconds  
**Snapshots**: 1,500

```bash
# Start collection and let it run
./scripts/collect_normal_data.sh

# Or use screen/tmux for long sessions
screen -S data-collection
./scripts/collect_normal_data.sh
# Detach: Ctrl+A, D
# Reattach: screen -r data-collection
```

**Advantages**:
- Captures various time-of-day patterns
- Natural workload variations
- Comprehensive normal behavior coverage

---

### Strategy 2: Multi-Session Collection

**Duration**: 3-4 hours per session × 5-6 sessions  
**Interval**: 45 seconds  
**Snapshots**: 300 per session

```bash
# Session 1: Morning (8am-11am)
./scripts/collect_normal_data.sh
# Collect 300 snapshots, then stop

# Session 2: Afternoon (2pm-5pm)
# Resume collection

# Session 3: Evening (8pm-11pm)
# Continue...
```

**Advantages**:
- Flexible scheduling
- Can monitor each session
- Captures different daily patterns

---

### Strategy 3: Distributed Collection

**Duration**: Parallel collection from multiple environments  
**Snapshots**: 500 from each environment

```bash
# Environment 1: Development cluster
./scripts/collect_normal_data.sh

# Environment 2: Staging cluster
./scripts/collect_normal_data.sh

# Environment 3: Production-like cluster
./scripts/collect_normal_data.sh
```

**Advantages**:
- Faster total collection time
- Diverse environment patterns
- Better generalization

---

## Monitoring Collection

### Real-Time Progress

```bash
# Watch collection log
tail -f logs/normal_collection_*.log

# Check snapshot count
ls -1 data/raw/snapshot_[0-9]*.json | wc -l

# Monitor cluster health
watch kubectl get pods --all-namespaces
```

### Health Checks During Collection

The automated script performs health checks every 50 snapshots:
- Pod count stability
- Resource utilization
- No unexpected failures

**Manual health check**:
```bash
# Check for any issues
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | tail -20

# Verify no restarts
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.status.containerStatuses[].restartCount > 0)'
```

---

## After Collection

### Step 1: Verify Data Quality

```bash
# Count collected snapshots
NORMAL_COUNT=$(ls -1 data/raw/snapshot_[0-9]*.json | wc -l)
echo "Normal snapshots: $NORMAL_COUNT"

# Should be around 1,500-1,600 total
```

### Step 2: Convert to CSV (if using Method 1)

```bash
# Activate virtual environment
source venv/bin/activate

# Run conversion
python scripts/convert_json_to_csv.py --input-dir data/raw --output-dir data/processed
```

### Step 3: Verify Class Balance

```bash
# Check new distribution
python -c "
import pandas as pd
df = pd.read_csv('data/processed/metadata.csv')
print('Class Distribution:')
print(df['scenario_type'].value_counts())
print('\nPercentages:')
print(df['scenario_type'].value_counts(normalize=True) * 100)
"
```

**Expected output**:
```
Class Distribution:
normal    1599
stress    1587
Name: count, dtype: int64

Percentages:
normal    50.2%
stress    49.8%
```

### Step 4: Merge Data (if using Method 2)

```bash
# Merge normal CSV files with existing data
python scripts/merge_csv_data.py
```

---

## Troubleshooting

### Issue: Collection Script Fails

**Symptoms**: Script exits with error

**Solutions**:
1. Check Prometheus connectivity:
   ```bash
   kubectl port-forward -n monitoring svc/prometheus 9090:9090
   curl http://localhost:9090/api/v1/query?query=up
   ```

2. Verify Python dependencies:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Check collector modules:
   ```bash
   python -c "from src.collectors.prometheus_collector import PrometheusCollector"
   ```

---

### Issue: Cluster Becomes Unstable

**Symptoms**: Pods restarting, high resource usage

**Solutions**:
1. Stop collection immediately (Ctrl+C)
2. Check what changed:
   ```bash
   kubectl get events --all-namespaces --sort-by='.lastTimestamp'
   ```
3. Wait for stability before resuming
4. Consider reducing collection frequency (increase interval to 60s)

---

### Issue: Disk Space Running Low

**Symptoms**: Collection fails with disk space error

**Solutions**:
1. Check available space:
   ```bash
   df -h
   ```

2. Clean up old data:
   ```bash
   # Archive old JSON files
   tar -czf data/archive/raw_$(date +%Y%m%d).tar.gz data/raw/*.json
   rm data/raw/snapshot_*.json
   ```

3. Use CSV collection (more space-efficient)

---

### Issue: Collection Too Slow

**Symptoms**: Taking longer than expected

**Solutions**:
1. Reduce interval (but maintain quality):
   ```bash
   # Edit script: COLLECTION_INTERVAL=30
   ```

2. Use parallel collection from multiple clusters

3. Collect during off-peak hours for faster Prometheus queries

---

## Best Practices

### ✅ DO

- **Collect during various times** (morning, afternoon, evening, night)
- **Monitor cluster health** throughout collection
- **Use screen/tmux** for long-running sessions
- **Keep logs** for troubleshooting
- **Verify data quality** after collection
- **Back up data** before merging

### ❌ DON'T

- **Don't collect during deployments** or cluster updates
- **Don't run chaos experiments** during normal data collection
- **Don't ignore health warnings** from the script
- **Don't delete raw data** until CSV conversion is verified
- **Don't mix normal and stress data** in the same collection session

---

## Collection Timeline

### Recommended Schedule

**Week 1: Initial Collection (500 snapshots)**
- Day 1-2: Setup and test (50 snapshots)
- Day 3-4: First major collection (250 snapshots)
- Day 5-6: Second collection (200 snapshots)

**Week 2: Complete Collection (1,000 snapshots)**
- Day 1-3: Continuous collection (600 snapshots)
- Day 4-5: Final collection (400 snapshots)
- Day 6-7: Verification and merging

**Total**: ~2 weeks for complete balanced dataset

---

## Success Criteria

✅ **Collection Complete When**:
1. Total normal snapshots ≥ 1,500
2. Class balance: 40-50% normal, 50-60% stress
3. Data quality checks pass
4. No significant gaps in temporal coverage
5. CSV files successfully generated

---

## Next Steps After Collection

1. **Data Validation**
   ```bash
   python scripts/validate_data.py
   ```

2. **Feature Engineering**
   - Normalize features
   - Create temporal sequences
   - Generate graph structures

3. **Train/Test Split**
   - Stratified split (70/15/15)
   - Temporal ordering preserved
   - Class balance maintained

4. **Begin GNN Training**
   - Start with baseline model
   - Evaluate on balanced dataset
   - Iterate and improve

---

## Support

If you encounter issues:
1. Check logs in `logs/normal_collection_*.log`
2. Review troubleshooting section above
3. Verify cluster health
4. Check Prometheus metrics

---

## Summary

**Goal**: Collect 1,500 normal scenario snapshots  
**Time**: 18-21 hours (continuous) or 2 weeks (distributed)  
**Method**: Choose automated script or direct CSV collection  
**Result**: Balanced dataset ready for GNN training

**Remember**: Quality over quantity. Ensure true normal conditions throughout collection!