# Data Collection Strategy for GNN-based K8s Failure Prevention

## Current Data Inventory

Based on analysis of your `data/raw/` directory:
- **Normal scenarios**: ~14 snapshots (snapshot_*.json)
- **Pre-failure scenarios**: ~159 snapshots (snapshot_pre_failure_*.json)
- **Current ratio**: ~1:11 (normal:stress)

## Data Structure Analysis

Each snapshot contains:
1. **Metrics** (time-series data):
   - Pod CPU usage
   - Pod memory usage
   - Node CPU usage
   - Node memory usage
   - API server latency
   - Pod restart counts

2. **Topology** (graph structure):
   - Pods (nodes in graph)
   - Nodes (K8s nodes)
   - Relationships (pod-to-node assignments)

3. **Label** (only in pre_failure snapshots):
   - Classification target for supervised learning

## Recommended Data Distribution

### For Binary Classification (Normal vs Pre-Failure)

**Recommended Ratio: 40-50% Normal : 50-60% Stress**

#### Why This Balance?

1. **Class Balance**: GNNs perform better with balanced datasets
2. **Real-world representation**: Production systems spend most time in normal state
3. **Avoid overfitting**: Too many stress scenarios can make model overly sensitive

#### Specific Recommendations:

**Minimum Dataset Size**: 500-1000 snapshots total
- Normal scenarios: 250-500 snapshots
- Stress/Pre-failure scenarios: 250-500 snapshots

**Optimal Dataset Size**: 2000-5000 snapshots total
- Normal scenarios: 1000-2500 snapshots
- Stress/Pre-failure scenarios: 1000-2500 snapshots

**Your Current Status**:
- ✅ You have 159 pre-failure snapshots (good start)
- ❌ You only have 14 normal snapshots (need ~145-500 more)

### For Multi-Class Classification (Normal, Warning, Critical, Failure)

If you plan to detect severity levels:
- Normal: 40%
- Warning: 25%
- Critical: 20%
- Failure: 15%

## Data Collection Strategy

### 1. Normal Scenario Collection

**What to collect**:
- Steady-state operations (30-60 min periods)
- Low to moderate load (20-60% resource utilization)
- No pod restarts or failures
- Stable API server latency (<100ms)
- Various time periods (different traffic patterns)

**Collection frequency**: Every 30-60 seconds

**Duration**: Collect for multiple days to capture:
- Different times of day
- Weekday vs weekend patterns
- Various workload patterns

### 2. Stress Scenario Collection

**What to collect**:
- Resource exhaustion scenarios (CPU, memory)
- Network latency issues
- Pod evictions and restarts
- API server overload
- Cascading failures
- Node failures

**Collection frequency**: Every 10-30 seconds (more frequent during stress)

**Time windows**:
- 5-10 minutes before failure
- During failure
- 5-10 minutes after recovery

### 3. Temporal Sequences

**Important**: Collect sequences, not just isolated snapshots
- Window size: 5-10 consecutive snapshots
- This captures temporal patterns and trends
- GNNs can learn from progression patterns

## CSV vs JSON: Format Recommendation

### Recommendation: **Use CSV for Training Data**

#### Why CSV is Better:

1. **Performance**:
   - 3-5x faster to load with pandas/numpy
   - Lower memory footprint
   - Better for large datasets

2. **ML Pipeline Integration**:
   - Direct compatibility with scikit-learn, PyTorch, TensorFlow
   - Easier feature engineering
   - Simpler data preprocessing

3. **Storage Efficiency**:
   - 30-50% smaller file sizes
   - Easier to version control
   - Faster I/O operations

4. **Debugging**:
   - Human-readable
   - Easy to inspect with standard tools
   - Simple to validate data quality

#### When to Keep JSON:

- Raw data collection (keep as backup)
- Complex nested structures (topology)
- API responses
- Configuration files

### Recommended Data Pipeline:

```
JSON (raw) → Preprocessing → CSV (features) → GNN Training
```

## Proposed CSV Schema

### 1. Node Features CSV (`node_features.csv`)
```csv
snapshot_id,node_id,node_type,cpu_usage,memory_usage,status,label
1774286375,pod-1,pod,0.45,512.5,Running,0
1774286375,pod-2,pod,0.78,1024.0,Running,0
1774286375,node-1,k8s_node,0.55,4096.0,Ready,0
```

### 2. Edge Features CSV (`edge_features.csv`)
```csv
snapshot_id,source_node,target_node,edge_type,weight
1774286375,pod-1,node-1,scheduled_on,1.0
1774286375,pod-2,node-1,scheduled_on,1.0
```

### 3. Graph-Level Features CSV (`graph_features.csv`)
```csv
snapshot_id,timestamp,total_pods,total_nodes,avg_cpu,avg_memory,api_latency,total_restarts,label
1774286375,2026-01-20T10:30:00,10,3,0.55,2048.0,45.2,0,0
```

### 4. Temporal Sequences CSV (`sequences.csv`)
```csv
sequence_id,snapshot_ids,label
seq_001,"1774286375,1774286705,1774286856",0
seq_002,"1774370660,1774370990,1774371051",1
```

## Data Augmentation Strategies

To increase your dataset size:

1. **Temporal Sliding Windows**:
   - Create overlapping sequences
   - Example: [t1,t2,t3], [t2,t3,t4], [t3,t4,t5]

2. **Synthetic Normal Data**:
   - Add Gaussian noise to existing normal snapshots
   - Interpolate between normal states
   - Bootstrap sampling

3. **Stress Scenario Variations**:
   - Vary failure intensity
   - Different failure types
   - Multiple simultaneous stressors

## Validation Strategy

### Train/Validation/Test Split:
- Training: 70%
- Validation: 15%
- Test: 15%

### Important Considerations:
1. **Temporal Split**: Don't shuffle randomly
   - Use chronological split to avoid data leakage
   - Train on earlier data, test on later data

2. **Stratified Split**: Maintain class balance in each split

3. **Cross-Validation**: Use time-series cross-validation
   - Rolling window approach
   - Respect temporal ordering

## Action Items

### Immediate (Week 1-2):
1. ✅ Collect 150-200 more normal scenario snapshots
2. ✅ Create preprocessing script to convert JSON → CSV
3. ✅ Implement data validation checks
4. ✅ Create train/val/test splits

### Short-term (Week 3-4):
1. ✅ Collect diverse stress scenarios (different failure types)
2. ✅ Implement temporal sequence extraction
3. ✅ Create data augmentation pipeline
4. ✅ Build feature engineering pipeline

### Long-term (Month 2+):
1. ✅ Continuous data collection in production
2. ✅ Active learning to identify edge cases
3. ✅ Periodic dataset rebalancing
4. ✅ Model retraining with new data

## Quality Metrics to Track

1. **Data Quality**:
   - Missing value percentage (<5%)
   - Outlier detection
   - Label consistency

2. **Dataset Balance**:
   - Class distribution
   - Temporal coverage
   - Scenario diversity

3. **Collection Metrics**:
   - Snapshots per day
   - Coverage of different scenarios
   - Data freshness

## Conclusion

**Summary**:
- Target: 500-1000 snapshots minimum (balanced 50:50)
- Current gap: Need ~150-500 more normal scenarios
- Format: Convert to CSV for training efficiency
- Strategy: Collect temporal sequences, not isolated snapshots
- Validation: Use temporal splits to avoid data leakage

**Next Steps**:
1. Set up automated normal scenario collection
2. Create JSON→CSV conversion pipeline
3. Implement data validation and quality checks
4. Begin feature engineering for GNN input