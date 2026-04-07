import time
import os
from etcd_failure_data_collector import collect_snapshot 

def collect_multiple_baselines(num_batches=10, window_minutes=2):
    """Automates the collection of 10 healthy snapshots."""
    print(f"🚀 Starting collection of {num_batches} baseline batches...")
    
    if not os.path.exists('/root/K8-Project/structure/data/baseline'):
        os.makedirs('/root/K8-Project/structure/data/baseline')

    for i in range(1, num_batches + 1):
        filename = f"/root/K8-Project/structure/data/baseline/healthy_batch_{i}.csv"
        print(f"📦 Collecting Batch {i}/{num_batches}...")
        
        # Collect with label 0
        collect_snapshot(window_minutes=window_minutes, label=0, output_file=filename)
        
        if i < num_batches:
            print(f"Waiting {window_minutes} minutes for the next window...")
            time.sleep(window_minutes * 60)

    print("✅ All baseline batches collected successfully.")

if __name__ == "__main__":
    collect_multiple_baselines()