# Node Exporter Setup Guide

## Why Node Exporter?

Node Exporter provides **system-level metrics** that are critical for detecting resource exhaustion failures:

### Current Limitations Without Node Exporter:
- ❌ Only pod-level CPU from cAdvisor
- ❌ No node memory pressure visibility
- ❌ Missing system load averages
- ❌ No disk I/O metrics at node level

### Benefits With Node Exporter:
- ✅ **Direct node CPU utilization** - Better CPU stress detection
- ✅ **Node memory availability** - Detect memory pressure before OOM
- ✅ **System load averages** - Understand overall node health
- ✅ **Disk I/O metrics** - Correlate with etcd performance
- ✅ **Network statistics** - Detect network bottlenecks

---

## Enhanced Feature Set

### Before (4 features):
```
[api_rate, etcd_fsync, pod_cpu, api_latency]
```

### After (7 features):
```
[api_rate, etcd_fsync, pod_cpu, api_latency, node_cpu, node_memory, node_load]
```

---

## Installation Steps

### 1. Deploy Node Exporter DaemonSet
```bash
kubectl apply -f setup/node-exporter-daemonset.yaml
```

This creates:
- DaemonSet running on **all nodes** (control-plane + workers)
- Service exposing metrics on port 9100
- Proper host mounts for `/proc`, `/sys`, `/root`

### 2. Update Prometheus Configuration
```bash
kubectl apply -f setup/prometheus-config.yaml
```

This adds a new scrape job:
```yaml
- job_name: 'node-exporter'
  kubernetes_sd_configs:
    - role: endpoints
      namespaces:
        names:
          - monitoring
```

### 3. Restart Prometheus
```bash
kubectl rollout restart deployment/prometheus-deployment -n monitoring
```

### 4. Verify Node Exporter is Running
```bash
# Check DaemonSet
kubectl get daemonset -n monitoring

# Check pods on all nodes
kubectl get pods -n monitoring -o wide | grep node-exporter

# Expected output: 4 pods (1 control-plane + 3 workers)
```

### 5. Verify Prometheus is Scraping
```bash
# Port-forward Prometheus
kubectl port-forward deploy/prometheus-deployment 9090:9090 -n monitoring

# Open browser: http://localhost:9090/targets
# Look for "node-exporter" job with 4 UP targets
```

### 6. Test Node Exporter Metrics
In Prometheus UI, query:
```promql
# Node CPU usage
100 - (avg by (node) (irate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)

# Node memory usage percentage
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))

# System load (1 minute average)
node_load1
```

---

## Key Metrics Collected

### CPU Metrics:
- `node_cpu_seconds_total` - Per-CPU time in different modes
- Calculated: `100 - idle%` = CPU utilization

### Memory Metrics:
- `node_memory_MemTotal_bytes` - Total RAM
- `node_memory_MemAvailable_bytes` - Available RAM
- Calculated: `(Total - Available) / Total * 100` = Memory usage %

### Load Metrics:
- `node_load1` - 1-minute load average
- `node_load5` - 5-minute load average
- `node_load15` - 15-minute load average

### Disk Metrics:
- `node_disk_io_time_seconds_total` - Disk I/O time
- `node_filesystem_avail_bytes` - Available disk space

### Network Metrics:
- `node_network_receive_bytes_total` - Network RX
- `node_network_transmit_bytes_total` - Network TX

---

## Impact on GNN Model

### Better Failure Detection:

**CPU Stress (Label 3)**:
- **Before**: Only pod CPU from cAdvisor
- **After**: Direct node CPU + system load → Better detection of node-wide CPU exhaustion

**Memory Stress (Label 4)**:
- **Before**: Container memory limits
- **After**: Actual node memory pressure → Detect OOM conditions earlier

**Etcd Stress (Label 1)**:
- **Before**: Only etcd fsync latency
- **After**: Correlate with node disk I/O → Understand if it's etcd or disk issue

**API Stress (Label 2)**:
- **Before**: API latency + request rate
- **After**: Add node CPU/memory → Detect if API slowness is due to resource constraints

### Enhanced Graph Features:

Each node in the graph now has **7-dimensional features**:
```python
Node Features = [
    api_rate,      # Control plane health
    etcd_fsync,    # Storage health
    pod_cpu,       # Workload health
    api_latency,   # API responsiveness
    node_cpu,      # System CPU pressure
    node_memory,   # System memory pressure
    node_load      # Overall system load
]
```

---

## Troubleshooting

### Node Exporter pods not starting:
```bash
kubectl describe pod -n monitoring -l app=node-exporter
```

### Metrics not appearing in Prometheus:
```bash
# Check if service endpoints exist
kubectl get endpoints -n monitoring node-exporter

# Check Prometheus logs
kubectl logs -n monitoring deployment/prometheus-deployment
```

### Permission issues:
Node Exporter needs `hostNetwork: true` and host mounts. Ensure:
- DaemonSet has proper security context
- Host paths are accessible

---

## Next Steps

After Node Exporter is running:

1. **Collect new data** with enhanced metrics:
   ```bash
   python3 structure/ingestor/master_collector.py
   ```

2. **Train updated model** with 7 input features:
   ```bash
   python3 structure/trainer/train.py
   ```

3. **Compare results**: The model should show improved accuracy, especially for CPU and memory stress scenarios.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│              Kubernetes Cluster                  │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Control-Plane│  │   Worker-1   │            │
│  │              │  │              │            │
│  │ Node Exporter│  │ Node Exporter│            │
│  │   :9100      │  │   :9100      │            │
│  └──────┬───────┘  └──────┬───────┘            │
│         │                  │                     │
│         └──────────┬───────┘                     │
│                    │                             │
│         ┌──────────▼──────────┐                 │
│         │    Prometheus       │                 │
│         │  (scrapes :9100)    │                 │
│         └──────────┬──────────┘                 │
│                    │                             │
└────────────────────┼─────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │  master_collector   │
          │  (queries metrics)  │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   CSV with 7 cols   │
          │  [api, etcd, pod,   │
          │   api_lat, node_cpu,│
          │   node_mem, load]   │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   GNN Model (7D)    │
          │  5-class classifier │
          └─────────────────────┘