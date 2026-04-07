import time
import os
import subprocess
import requests
import pandas as pd

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"

BASE_DIR = "/root/K8-Project/structure/data/baseline"
FAILURE_DIR = "/root/K8-Project/structure/data/failure"
CHAOS_DIR = "/root/K8-Project/structure/chaos"

def run_command(cmd):
    """Executes shell commands for kubectl."""
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Command Failed: {cmd}\nError: {e.stderr.decode()}")

def get_metrics(query, start, end, metric_name, label, step="15s"):
    params = {'query': query, 'start': start, 'end': end, 'step': step}
    rows = []
    try:
        r = requests.get(PROMETHEUS_URL, params=params)
        r.raise_for_status()
        results = r.json()['data']['result']
        for res in results:
            metadata = res['metric']
            # Standardizing entity naming
            entity = metadata.get('pod') or metadata.get('instance') or 'cluster'
            # Extracting the Node (Physical Host)
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
    """Saves data to either BASE_DIR or FAILURE_DIR based on mode."""
    # Logic to select the correct parent directory
    target_dir = BASE_DIR if mode == "baseline" else FAILURE_DIR
    os.makedirs(target_dir, exist_ok=True)

    # UPDATED: The 4-Feature Set for Multi-Class Diagnosis
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
            # Pivot to create the feature columns
            df = df.pivot_table(index=['timestamp', 'entity', 'node', 'label'], 
                               columns='metric', values='value').reset_index().fillna(0)
            
            # Ensure all 4 columns exist for the GNN input layer
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
    # 1. BASELINE COLLECTION (Label 0)
    print("🌿 PHASE 1: Collecting Healthy Baseline...")
    collect_batch("baseline", label=0, num_batches=10, window_min=1)

    # 2. ETCD FAILURE COLLECTION (Label 1)
    print("\n🔥 PHASE 2: Starting Etcd Stress...")
    run_command(f"kubectl apply -f {CHAOS_DIR}/etcd-disk-stresser.yaml")
    time.sleep(60) 
    collect_batch("etcd_failure", label=1, num_batches=10, window_min=1)
    
    print("🧹 Deleting Etcd Job...")
    run_command("kubectl delete job etcd-disk-stresser -n chaos")
    
    print("⏳ Waiting 2 mins for Cluster Cooldown (Etcd recovery)...")
    time.sleep(120)

    # 3. API SERVER FAILURE COLLECTION (Label 2)
    print("\n🌊 PHASE 3: Starting API Stressor...")
    run_command(f"kubectl apply -f {CHAOS_DIR}/api-request-saturation.yaml")
    time.sleep(60) 
    collect_batch("api_failure", label=2, num_batches=10, window_min=1)
    
    print("🧹 Deleting API Job...")
    run_command("kubectl delete job api-pressure -n chaos")
    
    print("✨ Orchestration Complete. All data stored in /structure/data/")

if __name__ == "__main__":
    main()