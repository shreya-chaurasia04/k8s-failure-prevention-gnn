# Data Collection for K8s Failure Prevention GNN

## Quick Start Guide

### Current Status
- ✅ **Converted**: 1,686 JSON snapshots → CSV format
- ⚠️ **CRITICAL**: Severe class imbalance detected
  - Normal: 99 (5.9%)
  - Stress: 1,587 (94.1%)
- 🎯 **Target**: Collect 1,500 additional normal snapshots

### Why This Matters
Your GNN model needs balanced data to learn properly. With 94% stress scenarios, the model will:
- Be biased toward predicting failures
- Generate high false positive rates
- Fail to recognize normal operations

**Target balance**: 40-50% normal, 50-60% stress scenarios

---

## Step-by-Step: Collect Normal Data

### Option 1: Automated Collection (Recommended)

**Best for**: Overnight/long-running collection

```bash
# 1. Ensure cluster is in normal state
kubectl get pods --all-namespaces
kubectl top nodes

# 2. Run automated collection script
./scripts/collect_normal_data.sh

# 3. Let it run for ~18-21 hours
# (Can use screen/tmux for long sessions)
```

**Features**:
- Automatic health checks
- Progress tracking with ETA
- Graceful interruption (Ctrl+C)
- Collects 1,500 snapshots at 45s intervals

---

### Option 2: Direct CSV Collection

**Best for**: Efficient, no conversion needed

```bash
# 1. Activate Python environment
source venv/bin/activate

# 2. Run CSV collection
python3 scripts/collect_normal_data_csv.py

# 3. Monitor progress
# Output goes directly to data/processed/
```

**Advantages**:
- No JSON→CSV conversion needed
- Smaller disk footprint
- Faster processing

---

### Option 3: Manual Collection (Testing)

**Best for**: Short sessions, testing

```bash
cd src/collectors
python3 collect_snapshots.py
# Press Ctrl+C to stop
```

---

## Pre-Collection Checklist

Before starting collection, verify:

```bash
# ✅ Cluster accessible
kubectl cluster-info

# ✅ Prometheus running
kubectl get pods -n monitoring -l app=prometheus

# ✅ No chaos experiments
kubectl get pods -n workload -l chaos=true
# Should return: No resources found

# ✅ All pods healthy
kubectl get pods --all-namespaces | grep -v Running
# Should be empty or only Completed jobs

# ✅ Moderate resource usage
kubectl top nodes
# CPU: 20-60%, Memory: stable
```

---

## Collection Strategies

### Strategy 1: Continuous (18-21 hours)
```bash
screen -S data-collection
./scripts/collect_normal_data.sh
# Detach: Ctrl+A, D
# Reattach: screen -r data-collection
```

### Strategy 2: Multi-Session (3-4 hours × 5-6 sessions)
```bash
# Morning session
./scripts/collect_normal_data.sh
# Collect 300 snapshots, stop

# Afternoon session
# Resume collection

# Evening session
# Continue...
```

### Strategy 3: Distributed (Parallel from multiple clusters)
```bash
# Dev cluster: 500 snapshots
# Staging cluster: 500 snapshots  
# Prod-like cluster: 500 snapshots
```

---

## Monitoring Collection

```bash
# Watch progress
tail -f logs/normal_collection_*.log

# Count snapshots
ls -1 data/raw/snapshot_[0-9]*.json | wc -l

# Monitor cluster
watch kubectl get pods --all-namespaces
```

---

## After Collection

### 1. Verify Data Quality

```bash
# Count normal snapshots
NORMAL_COUNT=$(ls -1 data/raw/snapshot_[0-9]*.json | wc -l)
echo "Normal snapshots: $NORMAL_COUNT"
# Should be ~1,500-1,600
```

### 2. Convert to CSV (if using Option 1)

```bash
source venv/bin/activate
python scripts/convert_json_to_csv.py --input-dir data/raw --output-dir data/processed
```

### 3. Check Class Balance

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/processed/metadata.csv')
print('Class Distribution:')
print(df['scenario_type'].value_counts())
print('\nPercentages:')
print(df['scenario_type'].value_counts(normalize=True) * 100)
"
```

**Expected**:
```
normal    ~1,600 (50%)
stress     1,587 (50%)
```

---

## Troubleshooting

### Collection fails
```bash
# Check Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090
curl http://localhost:9090/api/v1/query?query=up

# Verify dependencies
source venv/bin/activate
pip install -r requirements.txt
```

### Cluster unstable
```bash
# Stop collection (Ctrl+C)
# Check events
kubectl get events --all-namespaces --sort-by='.lastTimestamp'
# Wait for stability
```

### Disk space low
```bash
# Check space
df -h

# Archive old data
tar -czf data/archive/raw_$(date +%Y%m%d).tar.gz data/raw/*.json
rm data/raw/snapshot_*.json
```

---

## Timeline

**Week 1**: Initial collection (500 snapshots)
- Days 1-2: Setup and test
- Days 3-6: Major collection

**Week 2**: Complete collection (1,000 snapshots)
- Days 1-5: Continuous collection
- Days 6-7: Verification

**Total**: ~2 weeks for balanced dataset

---

## Success Criteria

✅ Collection complete when:
1. Total normal snapshots ≥ 1,500
2. Class balance: 40-50% normal
3. Data quality checks pass
4. CSV files generated successfully

---

## Next Steps

After collecting balanced data:

1. **Validate data**
   ```bash
   python scripts/validate_data.py
   ```

2. **Create train/test splits**
   - Stratified split (70/15/15)
   - Preserve temporal ordering

3. **Begin GNN training**
   - Use balanced dataset
   - Evaluate performance

---

## Documentation

- **Detailed Guide**: `docs/NORMAL_DATA_COLLECTION_GUIDE.md`
- **Data Strategy**: `docs/DATA_COLLECTION_STRATEGY.md`
- **Conversion Summary**: `docs/DATA_CONVERSION_SUMMARY.md`

---

## Quick Reference

| Task | Command |
|------|---------|
| Start automated collection | `./scripts/collect_normal_data.sh` |
| Start CSV collection | `python3 scripts/collect_normal_data_csv.py` |
| Check progress | `tail -f logs/normal_collection_*.log` |
| Count snapshots | `ls -1 data/raw/snapshot_*.json \| wc -l` |
| Convert to CSV | `python scripts/convert_json_to_csv.py` |
| Check balance | See "Check Class Balance" above |

---

## Support

For issues or questions:
1. Check `logs/normal_collection_*.log`
2. Review troubleshooting section
3. Verify cluster health
4. Check Prometheus connectivity

---

**Remember**: Quality over quantity! Ensure true normal conditions throughout collection.