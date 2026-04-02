#!/usr/bin/env python3
"""
Automated Normal Scenario Data Collection - Direct to CSV
Collects normal scenario snapshots and writes directly to CSV format.
Target: 1,500 normal snapshots to balance the dataset (currently 99/1686 = 5.9%)
"""

import sys
import os
import time
import csv
import statistics
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'collectors'))

try:
    from prometheus_collector import PrometheusCollector
    from k8s_collector import K8sCollector
except ImportError as e:
    print(f"Error importing collectors: {e}")
    print("Please ensure src/collectors modules are available")
    sys.exit(1)

# Configuration
TARGET_SNAPSHOTS = 1500
COLLECTION_INTERVAL = 45  # seconds
OUTPUT_DIR = Path('data/processed')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# CSV file paths
NODE_FEATURES_FILE = OUTPUT_DIR / 'node_features_normal.csv'
EDGE_FEATURES_FILE = OUTPUT_DIR / 'edge_features_normal.csv'
GRAPH_FEATURES_FILE = OUTPUT_DIR / 'graph_features_normal.csv'
METADATA_FILE = OUTPUT_DIR / 'metadata_normal.csv'

# CSV headers
NODE_HEADERS = ['snapshot_id', 'node_id', 'node_type', 'cpu_usage', 'memory_usage_bytes', 
                'memory_usage_mb', 'restart_count', 'status', 'namespace', 'assigned_node', 'app_label']
EDGE_HEADERS = ['snapshot_id', 'source_node', 'target_node', 'edge_type', 'weight']
GRAPH_HEADERS = ['snapshot_id', 'timestamp', 'total_pods', 'total_nodes', 'running_pods', 
                 'pending_pods', 'failed_pods', 'avg_pod_cpu', 'avg_node_cpu', 'max_pod_cpu',
                 'max_node_cpu', 'avg_pod_memory_mb', 'avg_node_memory_mb', 'max_pod_memory_mb',
                 'max_node_memory_mb', 'avg_api_latency_ms', 'max_api_latency_ms', 'total_restarts', 'label']
METADATA_HEADERS = ['snapshot_id', 'filename', 'timestamp', 'is_pre_failure', 'label', 'scenario_type']


class NormalDataCollector:
    """Collects normal scenario data and writes directly to CSV."""
    
    def __init__(self):
        self.prom = PrometheusCollector()
        self.k8s = K8sCollector()
        self.collected_count = 0
        self.start_time = time.time()
        
        # Initialize CSV files with headers if they don't exist
        self._init_csv_files()
    
    def _init_csv_files(self):
        """Initialize CSV files with headers if they don't exist."""
        if not NODE_FEATURES_FILE.exists():
            with open(NODE_FEATURES_FILE, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=NODE_HEADERS)
                writer.writeheader()
        
        if not EDGE_FEATURES_FILE.exists():
            with open(EDGE_FEATURES_FILE, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=EDGE_HEADERS)
                writer.writeheader()
        
        if not GRAPH_FEATURES_FILE.exists():
            with open(GRAPH_FEATURES_FILE, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=GRAPH_HEADERS)
                writer.writeheader()
        
        if not METADATA_FILE.exists():
            with open(METADATA_FILE, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=METADATA_HEADERS)
                writer.writeheader()
    
    def collect_snapshot(self):
        """Collect a single snapshot and write to CSV files."""
        try:
            snapshot_id = str(int(time.time()))
            timestamp = datetime.now().isoformat()
            
            # Collect data
            metrics = self.prom.collect_snapshot()
            topology = self.k8s.collect_topology()
            
            # Process and write node features
            node_features = self._process_node_features(snapshot_id, metrics, topology)
            self._append_to_csv(NODE_FEATURES_FILE, NODE_HEADERS, node_features)
            
            # Process and write edge features
            edge_features = self._process_edge_features(snapshot_id, topology)
            self._append_to_csv(EDGE_FEATURES_FILE, EDGE_HEADERS, edge_features)
            
            # Process and write graph features
            graph_feature = self._process_graph_features(snapshot_id, timestamp, metrics, topology)
            self._append_to_csv(GRAPH_FEATURES_FILE, GRAPH_HEADERS, [graph_feature])
            
            # Process and write metadata
            metadata = self._process_metadata(snapshot_id, timestamp)
            self._append_to_csv(METADATA_FILE, METADATA_HEADERS, [metadata])
            
            self.collected_count += 1
            return True
            
        except Exception as e:
            print(f"Error collecting snapshot: {e}")
            return False
    
    def _process_node_features(self, snapshot_id, metrics, topology):
        """Extract node features from metrics and topology."""
        features = []
        
        # Pod topology lookup
        pod_topology = {pod['name']: pod for pod in topology.get('pods', [])}
        
        # Process pod metrics
        pod_cpu = {item['metric']['pod']: float(item['value'][1]) 
                   for item in metrics.get('pod_cpu', [])}
        pod_memory = {item['metric']['pod']: float(item['value'][1]) 
                      for item in metrics.get('pod_memory', [])}
        pod_restarts = {item['metric']['pod']: float(item['value'][1])
                        for item in metrics.get('pod_restarts', [])}
        
        # Combine pod data
        all_pods = set(pod_cpu.keys()) | set(pod_memory.keys()) | set(pod_restarts.keys())
        
        for pod_name in all_pods:
            topo_info = pod_topology.get(pod_name, {})
            features.append({
                'snapshot_id': snapshot_id,
                'node_id': pod_name,
                'node_type': 'pod',
                'cpu_usage': pod_cpu.get(pod_name, 0.0),
                'memory_usage_bytes': pod_memory.get(pod_name, 0.0),
                'memory_usage_mb': pod_memory.get(pod_name, 0.0) / (1024 * 1024),
                'restart_count': pod_restarts.get(pod_name, 0.0),
                'status': topo_info.get('status', 'Unknown'),
                'namespace': topo_info.get('namespace', 'default'),
                'assigned_node': topo_info.get('node', ''),
                'app_label': topo_info.get('labels', {}).get('app', '')
            })
        
        # Process K8s node metrics
        node_cpu = {}
        for item in metrics.get('node_cpu', []):
            instance = item['metric']['instance']
            node_name = instance.split(':')[0]
            node_cpu[node_name] = float(item['value'][1])
        
        node_memory = {}
        for item in metrics.get('node_memory', []):
            instance = item['metric']['instance']
            node_name = instance.split(':')[0]
            node_memory[node_name] = float(item['value'][1])
        
        all_nodes = set(node_cpu.keys()) | set(node_memory.keys())
        
        for node_name in all_nodes:
            features.append({
                'snapshot_id': snapshot_id,
                'node_id': node_name,
                'node_type': 'k8s_node',
                'cpu_usage': node_cpu.get(node_name, 0.0),
                'memory_usage_bytes': node_memory.get(node_name, 0.0),
                'memory_usage_mb': node_memory.get(node_name, 0.0) / (1024 * 1024),
                'restart_count': 0.0,
                'status': 'Ready',
                'namespace': '',
                'assigned_node': '',
                'app_label': ''
            })
        
        return features
    
    def _process_edge_features(self, snapshot_id, topology):
        """Extract edge features from topology."""
        edges = []
        for pod in topology.get('pods', []):
            edges.append({
                'snapshot_id': snapshot_id,
                'source_node': pod['name'],
                'target_node': pod.get('node', ''),
                'edge_type': 'scheduled_on',
                'weight': 1.0
            })
        return edges
    
    def _process_graph_features(self, snapshot_id, timestamp, metrics, topology):
        """Extract graph-level features."""
        # Count pods and nodes
        total_pods = len(topology.get('pods', []))
        total_nodes = len(topology.get('nodes', []))
        
        # Calculate CPU metrics
        pod_cpu_values = [float(item['value'][1]) for item in metrics.get('pod_cpu', [])]
        node_cpu_values = [float(item['value'][1]) for item in metrics.get('node_cpu', [])]
        
        # Calculate memory metrics
        pod_memory_values = [float(item['value'][1]) for item in metrics.get('pod_memory', [])]
        node_memory_values = [float(item['value'][1]) for item in metrics.get('node_memory', [])]
        
        # Calculate API latency
        api_latency_values = [float(item['value'][1]) for item in metrics.get('apiserver_latency', [])]
        
        # Calculate restarts
        restart_values = [float(item['value'][1]) for item in metrics.get('pod_restarts', [])]
        
        # Count pod statuses
        pod_statuses = [pod['status'] for pod in topology.get('pods', [])]
        running_pods = sum(1 for status in pod_statuses if status == 'Running')
        pending_pods = sum(1 for status in pod_statuses if status == 'Pending')
        failed_pods = sum(1 for status in pod_statuses if status == 'Failed')
        
        return {
            'snapshot_id': snapshot_id,
            'timestamp': timestamp,
            'total_pods': total_pods,
            'total_nodes': total_nodes,
            'running_pods': running_pods,
            'pending_pods': pending_pods,
            'failed_pods': failed_pods,
            'avg_pod_cpu': statistics.mean(pod_cpu_values) if pod_cpu_values else 0.0,
            'avg_node_cpu': statistics.mean(node_cpu_values) if node_cpu_values else 0.0,
            'max_pod_cpu': max(pod_cpu_values) if pod_cpu_values else 0.0,
            'max_node_cpu': max(node_cpu_values) if node_cpu_values else 0.0,
            'avg_pod_memory_mb': statistics.mean(pod_memory_values) / (1024 * 1024) if pod_memory_values else 0.0,
            'avg_node_memory_mb': statistics.mean(node_memory_values) / (1024 * 1024) if node_memory_values else 0.0,
            'max_pod_memory_mb': max(pod_memory_values) / (1024 * 1024) if pod_memory_values else 0.0,
            'max_node_memory_mb': max(node_memory_values) / (1024 * 1024) if node_memory_values else 0.0,
            'avg_api_latency_ms': statistics.mean(api_latency_values) * 1000 if api_latency_values else 0.0,
            'max_api_latency_ms': max(api_latency_values) * 1000 if api_latency_values else 0.0,
            'total_restarts': sum(restart_values) if restart_values else 0.0,
            'label': 0  # Normal scenario
        }
    
    def _process_metadata(self, snapshot_id, timestamp):
        """Create metadata entry."""
        return {
            'snapshot_id': snapshot_id,
            'filename': f'snapshot_normal_{snapshot_id}.csv',
            'timestamp': timestamp,
            'is_pre_failure': False,
            'label': 0,
            'scenario_type': 'normal'
        }
    
    def _append_to_csv(self, filepath, headers, rows):
        """Append rows to CSV file."""
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerows(rows)
    
    def print_progress(self):
        """Print collection progress."""
        elapsed = time.time() - self.start_time
        progress = (self.collected_count / TARGET_SNAPSHOTS) * 100
        remaining = TARGET_SNAPSHOTS - self.collected_count
        eta_seconds = remaining * COLLECTION_INTERVAL
        eta_hours = eta_seconds // 3600
        eta_minutes = (eta_seconds % 3600) // 60
        
        print(f"✓ Collected {self.collected_count}/{TARGET_SNAPSHOTS} ({progress:.1f}%) | "
              f"ETA: {int(eta_hours)}h {int(eta_minutes)}m")


def main():
    print("="*60)
    print("Normal Scenario Data Collection (Direct to CSV)")
    print("="*60)
    print(f"Target: {TARGET_SNAPSHOTS} snapshots")
    print(f"Interval: {COLLECTION_INTERVAL}s")
    print(f"Output: {OUTPUT_DIR}")
    print("")
    
    # Check if files already exist
    existing_count = 0
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            existing_count = sum(1 for line in f) - 1  # Subtract header
        print(f"Found {existing_count} existing normal snapshots")
        print("")
    
    print("IMPORTANT: Ensure normal conditions:")
    print("  • No chaos experiments running")
    print("  • All pods in Running state")
    print("  • CPU usage: 20-60% (moderate load)")
    print("  • No recent pod restarts")
    print("")
    
    response = input("Ready to start collection? (yes/no): ")
    if response.lower() != 'yes':
        print("Collection cancelled")
        return
    
    print("")
    print("Starting collection... (Press Ctrl+C to stop)")
    print("")
    
    collector = NormalDataCollector()
    
    try:
        while collector.collected_count < TARGET_SNAPSHOTS:
            if collector.collect_snapshot():
                collector.print_progress()
                
                # Health check every 50 snapshots
                if collector.collected_count % 50 == 0 and collector.collected_count > 0:
                    print("")
                    print(f"Health check at snapshot {collector.collected_count}...")
                    print("✓ Continuing collection")
                    print("")
                
                if collector.collected_count < TARGET_SNAPSHOTS:
                    time.sleep(COLLECTION_INTERVAL)
            else:
                print("✗ Collection failed, retrying in 10s...")
                time.sleep(10)
    
    except KeyboardInterrupt:
        print("\n\nCollection interrupted by user")
    
    # Final summary
    print("")
    print("="*60)
    print("Collection Summary")
    print("="*60)
    print(f"Collected: {collector.collected_count} new snapshots")
    print(f"Total normal snapshots: {existing_count + collector.collected_count}")
    print(f"Target: {TARGET_SNAPSHOTS}")
    print(f"Progress: {(collector.collected_count / TARGET_SNAPSHOTS) * 100:.1f}%")
    print("")
    print("Output files:")
    print(f"  • {NODE_FEATURES_FILE}")
    print(f"  • {EDGE_FEATURES_FILE}")
    print(f"  • {GRAPH_FEATURES_FILE}")
    print(f"  • {METADATA_FILE}")
    print("")
    print("Next steps:")
    print("1. Merge with existing data: python scripts/merge_csv_data.py")
    print("2. Verify class balance")
    print("3. Begin GNN training")
    print("")


if __name__ == '__main__':
    main()

# Made with Bob
