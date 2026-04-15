#!/usr/bin/env python3
"""
Collect ONLY CPU and Memory stress data with 4 features (matching existing data).
"""

import time
import os
import subprocess
import requests
import pandas as pd

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
FAILURE_DIR = "structure/data/failure"
CHAOS_DIR = "structure/chaos"

def run_command(cmd):
    """Executes shell commands for kubectl."""
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Command Failed: {cmd}\nError: {e.stderr}")
        return False

def get_metrics(query, start, end, metric_name, label, step="15s"):
    params = {'query': query, 'start': start, 'end': end, 'step': step}
    rows = []
    try:
        r = requests.get(PROMETHEUS_URL, params=params, timeout=10)
        r.raise_for_status()
        results = r.json()['data']['result']
        for res in results:
            metadata = res['metric']
            entity = metadata.get('pod') or metadata.get('instance') or 'cluster'
            node = metadata.get('node') or metadata.get('instance') or 'n/a'
            
            for val in res['values']:
                rows.append({
                    'timestamp': val[0], 
                    'entity': entity, 
                    'node': node, 
                    'metric': metric_name, 
                    'value': float(val[1]), 
                    'label': label
                })
    except Exception as e:
        print(f"❌ Query failed for {metric_name}: {e}")
    return rows

def collect_batch(mode, label, num_batches=10, window_min=1):
    """Saves data with 4 features (matching existing data format)."""
    target_dir = FAILURE_DIR
    os.makedirs(target_dir, exist_ok=True)

    # 4-Feature Set (same as existing baseline/etcd/api data)
    queries = {
        "api_rate": 'sum(rate(apiserver_request_total[1m]))',
        "etcd_fsync": 'rate(etcd_disk_wal_fsync_duration_seconds_sum[1m])',
        "pod_cpu": 'rate(container_cpu_usage_seconds_total{namespace="workload"}[1m])',
        "api_latency": 'sum(rate(apiserver_request_duration_seconds_sum[1m])) / sum(rate(apiserver_request_total[1m]))'
    }

    for i in range(1, num_batches + 1):
        print(f"📊 [{mode.upper()}] Collecting Batch {i}/{num_batches}...")
        end = time.time()
        start = end - (window_min * 60)
        
        all_rows = []
        for m_name, q in queries.items():
            all_rows.extend(get_metrics(q, start, end, m_name, label))
        
        if all_rows:
            df = pd.DataFrame(all_rows)
            df = df.pivot_table(index=['timestamp', 'entity', 'node', 'label'], 
                               columns='metric', values='value').reset_index().fillna(0)
            
            # Ensure all 4 columns exist
            for col in queries.keys():
                if col not in df.columns:
                    df[col] = 0.0
                
            filename = os.path.join(target_dir, f"{mode}_batch_{i}.csv")
            df.to_csv(filename, index=False)
            print(f"✅ Saved to {filename}")
        
        if i < num_batches:
            print(f"🕒 Waiting {window_min}m for next snapshot...")
            time.sleep(window_min * 60)

def main():
    print("="*70)
    print("  COLLECTING CPU & MEMORY STRESS DATA (4 Features)")
    print("="*70 + "\n")
    
    print("This will collect:")
    print("  - CPU stress: 10 batches (Label 3)")
    print("  - Memory stress: 10 batches (Label 4)")
    print("\nFeatures: api_rate, etcd_fsync, pod_cpu, api_latency")
    print("Total time: ~20 minutes\n")
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    # Check Prometheus
    try:
        r = requests.get("http://localhost:9090/-/healthy", timeout=5)
        print("✅ Prometheus is accessible\n")
    except:
        print("❌ Prometheus not accessible at http://localhost:9090")
        print("   Run: kubectl port-forward deploy/prometheus-deployment 9090:9090 -n monitoring")
        return
    
    # CPU STRESS COLLECTION (Label 3)
    print("\n" + "="*70)
    print("PHASE 1: CPU STRESS (Label 3)")
    print("="*70 + "\n")
    
    print("🔥 Deploying CPU stressor on control-plane...")
    if not run_command(f"kubectl apply -f {CHAOS_DIR}/cpu-stress.yaml"):
        return
    
    print("⏳ Waiting 60s for stress to stabilize...")
    time.sleep(60)
    
    collect_batch("cpu_failure", label=3, num_batches=10, window_min=1)
    
    print("\n🧹 Deleting CPU Job...")
    run_command("kubectl delete job cpu-stressor -n chaos")
    
    print("⏳ Waiting 2 mins for control plane cooldown...")
    time.sleep(120)
    
    # MEMORY STRESS COLLECTION (Label 4)
    print("\n" + "="*70)
    print("PHASE 2: MEMORY STRESS (Label 4)")
    print("="*70 + "\n")
    
    print("💾 Deploying Memory stressor on control-plane...")
    if not run_command(f"kubectl apply -f {CHAOS_DIR}/memory-stress.yaml"):
        return
    
    print("⏳ Waiting 60s for stress to stabilize...")
    time.sleep(60)
    
    collect_batch("memory_failure", label=4, num_batches=10, window_min=1)
    
    print("\n🧹 Deleting Memory Job...")
    run_command("kubectl delete job memory-stressor -n chaos")
    
    print("\n" + "="*70)
    print("✨ DATA COLLECTION COMPLETE!")
    print("="*70 + "\n")
    
    print("📊 Collected:")
    print("   - structure/data/failure/cpu_failure_batch_1.csv to cpu_failure_batch_10.csv")
    print("   - structure/data/failure/memory_failure_batch_1.csv to memory_failure_batch_10.csv")
    print("\n📋 Data Format (4 features, matching existing data):")
    print("   - api_rate, etcd_fsync, pod_cpu, api_latency")
    print("\nNext steps:")
    print("   1. Train model: cd structure && python3 -m trainer.train && cd ..")
    print("   2. Test model: python3 structure/processor/test_model_with_new_stress.py")
    print("   3. Visualize: python3 structure/processor/generate_stress_visualizations.py")

if __name__ == "__main__":
    main()

# Made with Bob
