import json
import time
import os
from prometheus_collector import PrometheusCollector
from k8s_collector import K8sCollector
from datetime import datetime

# Get project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data/raw')
os.makedirs(DATA_DIR, exist_ok=True)

prom = PrometheusCollector()
k8s = K8sCollector()

print("Starting data collection (30s intervals)...")

while True:
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'metrics': prom.collect_snapshot(),
        'topology': k8s.collect_topology()
    }
    
    filename = os.path.join(DATA_DIR, f"snapshot_{int(time.time())}.json")
    with open(filename, 'w') as f:
        json.dump(snapshot, f, indent=2)
    
    print(f"✓ Collected {filename}")
    time.sleep(30)