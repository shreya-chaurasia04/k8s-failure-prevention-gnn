#!/usr/bin/env python3
"""
Collect ONLY Memory stress data (CPU already collected).
Uses Prometheus service directly instead of port-forward.
"""

import time
import os
import subprocess
import requests
import pandas as pd

# Use localhost with port-forward
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
        # Use kubectl proxy to access Prometheus
        r = requests.get(PROMETHEUS_URL, params=params, timeout=30)
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
    """Saves data with 4 features."""
    target_dir = FAILURE_DIR
    os.makedirs(target_dir, exist_ok=True)

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
            
            for col in queries.keys():
                if col not in df.columns:
                    df[col] = 0.0
                
            filename = os.path.join(target_dir, f"{mode}_batch_{i}.csv")
            df.to_csv(filename, index=False)
            print(f"✅ Saved to {filename}")
        else:
            print(f"⚠️  No data collected for batch {i}")
        
        if i < num_batches:
            print(f"🕒 Waiting {window_min}m for next snapshot...")
            time.sleep(window_min * 60)

def main():
    print("="*70)
    print("  COLLECTING MEMORY STRESS DATA ONLY")
    print("="*70 + "\n")
    
    print("Note: CPU data already collected successfully!")
    print("This will collect Memory stress data (10 batches, Label 4)\n")
    
    # Check if memory stressor is already running
    result = subprocess.run("kubectl get job memory-stressor -n chaos", 
                          shell=True, capture_output=True)
    if result.returncode == 0:
        print("✅ Memory stressor already running\n")
    else:
        print("💾 Deploying Memory stressor on control-plane...")
        if not run_command(f"kubectl apply -f {CHAOS_DIR}/memory-stress.yaml"):
            return
        print("⏳ Waiting 60s for stress to stabilize...")
        time.sleep(60)
    
    collect_batch("memory_failure", label=4, num_batches=10, window_min=1)
    
    print("\n🧹 Deleting Memory Job...")
    run_command("kubectl delete job memory-stressor -n chaos")
    
    print("\n" + "="*70)
    print("✨ MEMORY DATA COLLECTION COMPLETE!")
    print("="*70 + "\n")
    
    print("📊 You now have:")
    print("   - CPU failure data: cpu_failure_batch_1-10.csv")
    print("   - Memory failure data: memory_failure_batch_1-10.csv")
    print("\nNext steps:")
    print("   1. Train: cd structure && python3 -m trainer.train && cd ..")
    print("   2. Test: python3 structure/processor/test_model_with_new_stress.py")
    print("   3. Visualize: python3 structure/processor/generate_stress_visualizations.py")

if __name__ == "__main__":
    main()

# Made with Bob
