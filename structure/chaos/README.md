# Chaos Engineering Scenarios

This directory contains Kubernetes Job manifests for injecting various failure scenarios into the cluster to collect labeled training data for the GNN failure prediction model.

## Available Chaos Scenarios

### 1. **etcd-disk-stresser.yaml** (Label 1)
**Purpose**: Simulates etcd storage bottlenecks

**Mechanism**:
- Runs on control-plane node
- Uses `stress` tool with `--hdd 4 --hdd-bytes 512M`
- Continuously writes 512MB to disk with 4 workers
- Duration: 10 minutes (600s)

**Impact**:
- Increases etcd WAL fsync latency
- Slows down cluster state persistence
- Can cause API server delays

**Metrics Affected**:
- `etcd_disk_wal_fsync_duration_seconds_sum` ↑
- `api_latency` ↑ (secondary effect)

---

### 2. **api-request-saturation.yaml** (Label 2)
**Purpose**: Simulates API server overload

**Mechanism**:
- Spawns 3 parallel pods
- Each pod continuously queries:
  - `kubectl get pods -A`
  - `kubectl get events -A`
  - `kubectl get configmaps -A`
  - `kubectl get secrets -A`
- Sleep interval: 0.2s between batches

**Impact**:
- Saturates API server request queue
- Increases API response latency
- Can cause request throttling

**Metrics Affected**:
- `apiserver_request_total` ↑
- `apiserver_request_duration_seconds_sum` ↑
- `api_latency` ↑

---

### 3. **cpu-stress.yaml** (Label 3)
**Purpose**: Simulates CPU exhaustion on **control-plane node**

**Mechanism**:
- Runs on control-plane node using `nodeSelector`
- Uses `stress` tool with `--cpu 4`
- Spawns 4 workers spinning on sqrt()
- Resource limits: 2000m CPU
- Duration: 10 minutes (600s)
- Tolerates control-plane taints

**Impact on Control Plane**:
- **kube-apiserver**: Slower request processing
- **kube-scheduler**: Delayed scheduling decisions
- **kube-controller-manager**: Slower reconciliation loops
- **etcd**: Reduced throughput for state updates
- Overall cluster responsiveness degrades

**Metrics Affected**:
- `node_cpu` ↑ (control-plane node)
- `node_load` ↑ (system load average)
- `api_latency` ↑ (secondary effect)
- `apiserver_request_duration` ↑

---

### 4. **memory-stress.yaml** (Label 4)
**Purpose**: Simulates memory pressure on **control-plane node**

**Mechanism**:
- Runs on control-plane node using `nodeSelector`
- Uses `stress` tool with `--vm 2 --vm-bytes 512M`
- Allocates/frees 1GB total (2 workers × 512MB)
- Continuous malloc()/free() with `--vm-hang 0`
- Resource limits: 1Gi memory
- Duration: 10 minutes (600s)
- Tolerates control-plane taints

**Impact on Control Plane**:
- **kube-apiserver**: Memory pressure, potential OOM
- **etcd**: Reduced cache efficiency, slower reads
- **kube-scheduler**: Queue processing delays
- **kube-controller-manager**: Watch cache pressure
- Can trigger Linux OOM killer on control plane
- May cause control plane pod restarts

**Metrics Affected**:
- `node_memory` ↑ (control-plane node)
- `node_memory_MemAvailable_bytes` ↓
- `api_latency` ↑ (secondary effect)
- Potential control plane pod restarts

---

## Usage

### Deploy a Chaos Scenario
```bash
kubectl apply -f structure/chaos/cpu-stress.yaml
```

### Monitor the Chaos Job
```bash
kubectl get jobs -n chaos
kubectl get pods -n chaos
kubectl logs -n chaos <pod-name>
```

### Clean Up
```bash
kubectl delete job cpu-stressor -n chaos
kubectl delete job memory-stressor -n chaos
kubectl delete job etcd-disk-stresser -n chaos
kubectl delete job api-pressure -n chaos
```

---

## Automated Collection

The `master_collector.py` script orchestrates all 5 scenarios automatically:

1. **Baseline** (Label 0) - 10 batches of healthy state
2. **Etcd Stress** (Label 1) - 10 batches during disk stress
3. **API Saturation** (Label 2) - 10 batches during API overload
4. **CPU Stress** (Label 3) - 10 batches during CPU exhaustion
5. **Memory Stress** (Label 4) - 10 batches during memory pressure

Each phase includes:
- 60s warmup after job deployment
- 10 × 1-minute data collection windows
- 120s cooldown between scenarios

---

## Safety Notes

⚠️ **These jobs intentionally stress your cluster**:
- Run in a **test/development environment only**
- Ensure adequate cluster resources
- Monitor cluster health during execution
- Jobs have built-in timeouts (600s)
- Use `kubectl delete` to stop early if needed

---

## Label Mapping

| Label | Scenario | File Prefix |
|-------|----------|-------------|
| 0 | Healthy Baseline | `baseline_batch_*.csv` |
| 1 | Etcd Disk Stress | `etcd_failure_batch_*.csv` |
| 2 | API Saturation | `api_failure_batch_*.csv` |
| 3 | CPU Stress | `cpu_failure_batch_*.csv` |
| 4 | Memory Stress | `memory_failure_batch_*.csv` |