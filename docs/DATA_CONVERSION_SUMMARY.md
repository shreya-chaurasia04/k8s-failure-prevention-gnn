# Data Conversion Summary - JSON to CSV

## Conversion Completed Successfully ✅

**Date**: April 1, 2026  
**Input**: 1,686 JSON snapshot files  
**Output**: 4 CSV files in `data/processed/`

---

## Output Files

### 1. **metadata.csv** (1,686 rows)
Contains snapshot-level metadata and labels.

**Columns**:
- `snapshot_id`: Unique identifier (timestamp)
- `filename`: Original JSON filename
- `timestamp`: ISO 8601 timestamp
- `is_pre_failure`: Boolean flag
- `label`: Classification label (0 for normal, "pre_failure" for stress)
- `scenario_type`: "normal" or "stress"

### 2. **graph_features.csv** (1,686 rows)
Graph-level aggregated metrics for each snapshot.

**Columns** (19 total):
- `snapshot_id`, `timestamp`
- Pod counts: `total_pods`, `running_pods`, `pending_pods`, `failed_pods`
- Node count: `total_nodes`
- CPU metrics: `avg_pod_cpu`, `avg_node_cpu`, `max_pod_cpu`, `max_node_cpu`
- Memory metrics: `avg_pod_memory_mb`, `avg_node_memory_mb`, `max_pod_memory_mb`, `max_node_memory_mb`
- API metrics: `avg_api_latency_ms`, `max_api_latency_ms`
- Reliability: `total_restarts`
- Target: `label`

### 3. **node_features.csv** (16,750 rows)
Per-node (pod/k8s_node) features across all snapshots.

**Columns**:
- `snapshot_id`: Links to parent snapshot
- `node_id`: Pod or node name
- `node_type`: "pod" or "k8s_node"
- `cpu_usage`: CPU utilization
- `memory_usage_bytes`, `memory_usage_mb`: Memory metrics
- `restart_count`: Container restarts
- `status`: Pod/node status
- `namespace`, `assigned_node`, `app_label`: Topology info

### 4. **edge_features.csv** (11,703 rows)
Pod-to-node relationships (edges in the graph).

**Columns**:
- `snapshot_id`: Links to parent snapshot
- `source_node`: Pod name
- `target_node`: K8s node name
- `edge_type`: "scheduled_on"
- `weight`: Edge weight (1.0)

---

## Dataset Statistics

### Class Distribution

| Scenario Type | Count | Percentage |
|--------------|-------|------------|
| **Stress** (pre-failure) | 1,587 | 94.1% |
| **Normal** | 99 | 5.9% |

⚠️ **CRITICAL IMBALANCE DETECTED**

### Graph-Level Statistics

| Metric | Mean | Std | Min | Max |
|--------|------|-----|-----|-----|
| Total Pods | 6.94 | 0.24 | 6 | 7 |
| Avg Pod CPU | 0.032 | 0.051 | 0.0 | 0.156 |
| Avg Memory (MB) | varies | varies | - | - |
| API Latency (ms) | 178M | 28M | 0 | 209M |
| Total Restarts | 12.76 | 10.09 | 0 | 35 |

---

## Data Quality Assessment

### ✅ Strengths
1. **Complete conversion**: All 1,686 JSON files successfully processed
2. **Rich features**: 19 graph-level features captured
3. **Temporal data**: Timestamps preserved for time-series analysis
4. **Graph structure**: Node and edge features properly extracted
5. **Clean format**: CSV files ready for ML pipelines

### ⚠️ Critical Issues

#### 1. **Severe Class Imbalance**
- **Current**: 94% stress, 6% normal
- **Recommended**: 40-50% normal, 50-60% stress
- **Action needed**: Collect ~1,400-1,500 more normal scenario snapshots

#### 2. **Limited Normal Scenarios**
- Only 99 normal snapshots vs 1,587 stress snapshots
- Risk of model bias toward predicting failures
- May cause high false positive rate in production

---

## Recommendations

### Immediate Actions (Priority 1)

1. **Collect More Normal Data**
   ```bash
   # Target: 1,400-1,500 additional normal snapshots
   # Collection frequency: Every 30-60 seconds
   # Duration: Multiple days to capture various patterns
   ```

2. **Data Augmentation**
   - Create temporal sliding windows
   - Add Gaussian noise to normal scenarios
   - Bootstrap sampling for minority class

3. **Stratified Sampling**
   - Use stratified train/test split
   - Maintain class balance in validation sets
   - Consider SMOTE or class weighting

### Data Collection Strategy

**For Normal Scenarios**:
- Steady-state operations (30-60 min periods)
- Low to moderate load (20-60% utilization)
- No pod restarts or failures
- Stable API latency (<100ms)
- Various time periods (day/night, weekday/weekend)

**Collection Frequency**: Every 30-60 seconds  
**Target Duration**: 7-14 days continuous collection

---

## File Sizes

```
edge_features.csv:     880 KB
graph_features.csv:    391 KB
metadata.csv:          161 KB
node_features.csv:     1.9 MB
---
Total:                 3.3 MB
```

---

## Usage Examples

### Load Data with Pandas

```python
import pandas as pd

# Load all CSV files
metadata = pd.read_csv('data/processed/metadata.csv')
graph_features = pd.read_csv('data/processed/graph_features.csv')
node_features = pd.read_csv('data/processed/node_features.csv')
edge_features = pd.read_csv('data/processed/edge_features.csv')

# Check class distribution
print(metadata['scenario_type'].value_counts())

# Get features for a specific snapshot
snapshot_id = '1774286375'
graph_data = graph_features[graph_features['snapshot_id'] == snapshot_id]
nodes = node_features[node_features['snapshot_id'] == snapshot_id]
edges = edge_features[edge_features['snapshot_id'] == snapshot_id]
```

### Create Train/Test Split

```python
from sklearn.model_selection import train_test_split

# Stratified split to maintain class balance
train_meta, test_meta = train_test_split(
    metadata, 
    test_size=0.2, 
    stratify=metadata['scenario_type'],
    random_state=42
)

# Get corresponding features
train_ids = train_meta['snapshot_id'].values
test_ids = test_meta['snapshot_id'].values

train_graphs = graph_features[graph_features['snapshot_id'].isin(train_ids)]
test_graphs = graph_features[graph_features['snapshot_id'].isin(test_ids)]
```

---

## Next Steps

1. ✅ **Completed**: JSON to CSV conversion
2. ⏳ **In Progress**: Data quality assessment
3. 🔜 **Next**: Collect additional normal scenarios
4. 🔜 **Next**: Create data validation script
5. 🔜 **Next**: Update data collection pipeline for direct CSV output
6. 🔜 **Next**: Implement data augmentation
7. 🔜 **Next**: Build GNN training pipeline

---

## Conversion Script

The conversion was performed using:
- **Script**: `scripts/convert_json_to_csv.py`
- **Environment**: Python virtual environment with pandas 2.3.3 and numpy 2.0.2
- **Execution time**: ~23 seconds for 1,686 files
- **Memory usage**: Efficient streaming processing

To re-run conversion:
```bash
source venv/bin/activate
python scripts/convert_json_to_csv.py --input-dir data/raw --output-dir data/processed
```

---

## Conclusion

✅ **Conversion successful** - All data now in CSV format  
⚠️ **Action required** - Severe class imbalance must be addressed  
📊 **Ready for ML** - CSV files compatible with pandas, PyTorch, TensorFlow  
🎯 **Next priority** - Collect 1,400+ normal scenario snapshots