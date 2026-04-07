import requests
import pandas as pd
import time
import os

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"

def get_metrics(query, start, end, metric_name, label, step="15s"):
    params = {'query': query, 'start': start, 'end': end, 'step': step}
    rows = []
    try:
        r = requests.get(PROMETHEUS_URL, params=params)
        r.raise_for_status()
        results = r.json()['data']['result']
        
        for res in results:
            metadata = res['metric']
            # Dynamic entity identification
            entity = metadata.get('pod') or metadata.get('instance') or metadata.get('node') or 'cluster'
            
            for val in res['values']:
                rows.append({
                    'timestamp': val[0],
                    'entity': entity,
                    'metric': metric_name,
                    'value': float(val[1]),
                    'label': label
                })
    except Exception as e:
        print(f"Query failed: {query}. Error: {e}")
    return rows

def collect_snapshot(window_minutes=5, label=1, output_file="temp_batch.csv"):
    end = time.time()
    start = end - (window_minutes * 60)
    
    queries = {
        "api_rate": 'sum(rate(apiserver_request_total[1m]))',
        "etcd_fsync": 'rate(etcd_disk_wal_fsync_duration_seconds_sum[1m])',
        "pod_cpu": 'rate(container_cpu_usage_seconds_total{namespace="workload"}[1m])'
    }
    
    all_rows = []
    for metric_name, q in queries.items():
        all_rows.extend(get_metrics(q, start, end, metric_name, label))
    
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.pivot_table(index=['timestamp', 'entity', 'label'], 
                           columns='metric', 
                           values='value').reset_index().fillna(0)
        df.to_csv(output_file, index=False)
        print(f"✅ Failure data saved to {output_file}")
    return df

def collect_multiple_failures(num_batches=10, window_minutes=1):
    """Automates the collection of 10 failuresnapshots."""
    output_dir = "/root/K8-Project/structure/data/failure"
    print(f"🚀 Starting automated collection of {num_batches} FAILURE batches...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i in range(1, num_batches + 1):
        filename = f"{output_dir}/etcd_failure_batch_{i}.csv"
        print(f"📦 Collecting Failure Batch {i}/{num_batches}...")
        
        # We pass label=1 for failure data
        collect_snapshot(window_minutes=window_minutes, label=1, output_file=filename)
        
        if i < num_batches:
            # We wait so that each CSV contains a slightly different window of the failure
            print(f"Waiting {window_minutes} minutes for the next window...")
            time.sleep(window_minutes * 60)

    print("✅ All failure batches collected successfully.")

if __name__ == "__main__":
    # Ensure your Chaos Job is RUNNING before starting this!
    collect_multiple_failures()