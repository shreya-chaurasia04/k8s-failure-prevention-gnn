import json
import time
import os
from prometheus_collector import PrometheusCollector
from k8s_collector import K8sCollector
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data/raw')
os.makedirs(DATA_DIR, exist_ok=True)

prom = PrometheusCollector()
k8s = K8sCollector()

# Collect labeled data
label = input("Current state (normal/pre_failure/failure): ").strip()

print(f"Collecting with label: {label}")
print("Press Ctrl+C to stop")

while True:
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'metrics': prom.collect_snapshot(),
        'topology': k8s.collect_topology(),
        'label': label  # Add label
    }
    
    filename = os.path.join(DATA_DIR, f"snapshot_{label}_{int(time.time())}.json")
    with open(filename, 'w') as f:
        json.dump(snapshot, f, indent=2)
    
    print(f"✓ {filename}")
    time.sleep(30)
