#!/usr/bin/env python3
"""
Convert K8s snapshot JSON files to CSV format for GNN training.

This script processes JSON snapshots and creates multiple CSV files:
1. node_features.csv - Per-node (pod/k8s_node) features
2. edge_features.csv - Pod-to-node relationships
3. graph_features.csv - Graph-level aggregated metrics
4. metadata.csv - Snapshot metadata and labels
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import argparse
from datetime import datetime
import logging
import statistics

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
    HAS_NUMPY = True
except ImportError:
    HAS_PANDAS = False
    HAS_NUMPY = False
    print("Warning: pandas/numpy not found. Installing...")
    import subprocess
    subprocess.check_call(['pip3', 'install', 'pandas', 'numpy'])
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
    HAS_NUMPY = True

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JSONToCSVConverter:
    """Convert K8s JSON snapshots to CSV format."""
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize dataframes
        self.node_features_list = []
        self.edge_features_list = []
        self.graph_features_list = []
        self.metadata_list = []
    
    def extract_snapshot_id(self, filename: str) -> str:
        """Extract snapshot ID from filename."""
        # Extract timestamp from filename (e.g., snapshot_1774286375.json -> 1774286375)
        parts = filename.replace('.json', '').split('_')
        return parts[-1]
    
    def process_pod_metrics(self, snapshot_id: str, metrics: Dict, topology: Dict) -> List[Dict]:
        """Extract pod-level features."""
        node_features = []
        
        # Create pod lookup for topology info
        pod_topology = {pod['name']: pod for pod in topology.get('pods', [])}
        
        # Process CPU metrics
        pod_cpu = {item['metric']['pod']: float(item['value'][1]) 
                   for item in metrics.get('pod_cpu', [])}
        
        # Process memory metrics
        pod_memory = {item['metric']['pod']: float(item['value'][1]) 
                      for item in metrics.get('pod_memory', [])}
        
        # Process restart counts
        pod_restarts = {}
        for item in metrics.get('pod_restarts', []):
            pod_name = item['metric']['pod']
            restarts = float(item['value'][1])
            pod_restarts[pod_name] = restarts
        
        # Combine all pod metrics
        all_pods = set(pod_cpu.keys()) | set(pod_memory.keys()) | set(pod_restarts.keys())
        
        for pod_name in all_pods:
            topo_info = pod_topology.get(pod_name, {})
            
            feature = {
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
            }
            node_features.append(feature)
        
        return node_features
    
    def process_node_metrics(self, snapshot_id: str, metrics: Dict, topology: Dict) -> List[Dict]:
        """Extract K8s node-level features."""
        node_features = []
        
        # Create node lookup for topology info
        node_topology = {node['name']: node for node in topology.get('nodes', [])}
        
        # Process node CPU metrics
        node_cpu = {}
        for item in metrics.get('node_cpu', []):
            instance = item['metric']['instance']
            # Extract node name from instance (e.g., "minikube:10250" -> "minikube")
            node_name = instance.split(':')[0]
            node_cpu[node_name] = float(item['value'][1])
        
        # Process node memory metrics
        node_memory = {}
        for item in metrics.get('node_memory', []):
            instance = item['metric']['instance']
            node_name = instance.split(':')[0]
            node_memory[node_name] = float(item['value'][1])
        
        # Combine all node metrics
        all_nodes = set(node_cpu.keys()) | set(node_memory.keys())
        
        for node_name in all_nodes:
            topo_info = node_topology.get(node_name, {})
            
            feature = {
                'snapshot_id': snapshot_id,
                'node_id': node_name,
                'node_type': 'k8s_node',
                'cpu_usage': node_cpu.get(node_name, 0.0),
                'memory_usage_bytes': node_memory.get(node_name, 0.0),
                'memory_usage_mb': node_memory.get(node_name, 0.0) / (1024 * 1024),
                'restart_count': 0.0,  # Nodes don't restart
                'status': 'Ready',  # Assume ready if in metrics
                'namespace': '',  # Nodes don't have namespaces
                'assigned_node': '',  # Self-reference
                'app_label': ''
            }
            node_features.append(feature)
        
        return node_features
    
    def process_edges(self, snapshot_id: str, topology: Dict) -> List[Dict]:
        """Extract pod-to-node edges."""
        edges = []
        
        for pod in topology.get('pods', []):
            edge = {
                'snapshot_id': snapshot_id,
                'source_node': pod['name'],
                'target_node': pod.get('node', ''),
                'edge_type': 'scheduled_on',
                'weight': 1.0
            }
            edges.append(edge)
        
        return edges
    
    def process_graph_features(self, snapshot_id: str, timestamp: str,
                               metrics: Dict, topology: Dict, label: Optional[Union[str, int]] = None) -> Dict:
        """Extract graph-level aggregated features."""
        
        # Count pods and nodes
        total_pods = len(topology.get('pods', []))
        total_nodes = len(topology.get('nodes', []))
        
        # Calculate average CPU
        pod_cpu_values = [float(item['value'][1]) for item in metrics.get('pod_cpu', [])]
        node_cpu_values = [float(item['value'][1]) for item in metrics.get('node_cpu', [])]
        avg_pod_cpu = statistics.mean(pod_cpu_values) if pod_cpu_values else 0.0
        avg_node_cpu = statistics.mean(node_cpu_values) if node_cpu_values else 0.0
        
        # Calculate average memory
        pod_memory_values = [float(item['value'][1]) for item in metrics.get('pod_memory', [])]
        node_memory_values = [float(item['value'][1]) for item in metrics.get('node_memory', [])]
        avg_pod_memory = statistics.mean(pod_memory_values) if pod_memory_values else 0.0
        avg_node_memory = statistics.mean(node_memory_values) if node_memory_values else 0.0
        
        # Calculate API server latency
        api_latency_values = [float(item['value'][1]) for item in metrics.get('apiserver_latency', [])]
        avg_api_latency = statistics.mean(api_latency_values) if api_latency_values else 0.0
        max_api_latency = max(api_latency_values) if api_latency_values else 0.0
        
        # Calculate total restarts
        restart_values = [float(item['value'][1]) for item in metrics.get('pod_restarts', [])]
        total_restarts = sum(restart_values) if restart_values else 0.0
        
        # Count pod statuses
        pod_statuses = [pod['status'] for pod in topology.get('pods', [])]
        running_pods = sum(1 for status in pod_statuses if status == 'Running')
        pending_pods = sum(1 for status in pod_statuses if status == 'Pending')
        failed_pods = sum(1 for status in pod_statuses if status == 'Failed')
        
        graph_feature = {
            'snapshot_id': snapshot_id,
            'timestamp': timestamp,
            'total_pods': total_pods,
            'total_nodes': total_nodes,
            'running_pods': running_pods,
            'pending_pods': pending_pods,
            'failed_pods': failed_pods,
            'avg_pod_cpu': avg_pod_cpu,
            'avg_node_cpu': avg_node_cpu,
            'max_pod_cpu': max(pod_cpu_values) if pod_cpu_values else 0.0,
            'max_node_cpu': max(node_cpu_values) if node_cpu_values else 0.0,
            'avg_pod_memory_mb': avg_pod_memory / (1024 * 1024),
            'avg_node_memory_mb': avg_node_memory / (1024 * 1024),
            'max_pod_memory_mb': max(pod_memory_values) / (1024 * 1024) if pod_memory_values else 0.0,
            'max_node_memory_mb': max(node_memory_values) / (1024 * 1024) if node_memory_values else 0.0,
            'avg_api_latency_ms': avg_api_latency * 1000,  # Convert to ms
            'max_api_latency_ms': max_api_latency * 1000,
            'total_restarts': total_restarts,
            'label': label if label is not None else 0
        }
        
        return graph_feature
    
    def process_metadata(self, snapshot_id: str, filename: str,
                        timestamp: str, label: Optional[Union[str, int]] = None) -> Dict:
        """Extract metadata for each snapshot."""
        is_pre_failure = 'pre_failure' in filename
        
        metadata = {
            'snapshot_id': snapshot_id,
            'filename': filename,
            'timestamp': timestamp,
            'is_pre_failure': is_pre_failure,
            'label': label if label is not None else (1 if is_pre_failure else 0),
            'scenario_type': 'stress' if is_pre_failure else 'normal'
        }
        
        return metadata
    
    def process_single_file(self, json_file: Path) -> None:
        """Process a single JSON file."""
        try:
            logger.info(f"Processing {json_file.name}...")
            
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            snapshot_id = self.extract_snapshot_id(json_file.name)
            timestamp = data.get('timestamp', '')
            metrics = data.get('metrics', {})
            topology = data.get('topology', {})
            label = data.get('label')
            
            # Process pod features
            pod_features = self.process_pod_metrics(snapshot_id, metrics, topology)
            self.node_features_list.extend(pod_features)
            
            # Process node features
            node_features = self.process_node_metrics(snapshot_id, metrics, topology)
            self.node_features_list.extend(node_features)
            
            # Process edges
            edges = self.process_edges(snapshot_id, topology)
            self.edge_features_list.extend(edges)
            
            # Process graph-level features
            graph_feature = self.process_graph_features(snapshot_id, timestamp, metrics, topology, label)
            self.graph_features_list.append(graph_feature)
            
            # Process metadata
            metadata = self.process_metadata(snapshot_id, json_file.name, timestamp, label)
            self.metadata_list.append(metadata)
            
        except Exception as e:
            logger.error(f"Error processing {json_file.name}: {str(e)}")
    
    def save_csv_files(self) -> None:
        """Save all collected data to CSV files."""
        logger.info("Saving CSV files...")
        
        # Save node features
        if self.node_features_list:
            df_nodes = pd.DataFrame(self.node_features_list)
            output_path = self.output_dir / 'node_features.csv'
            df_nodes.to_csv(output_path, index=False)
            logger.info(f"Saved {len(df_nodes)} node features to {output_path}")
        
        # Save edge features
        if self.edge_features_list:
            df_edges = pd.DataFrame(self.edge_features_list)
            output_path = self.output_dir / 'edge_features.csv'
            df_edges.to_csv(output_path, index=False)
            logger.info(f"Saved {len(df_edges)} edges to {output_path}")
        
        # Save graph features
        if self.graph_features_list:
            df_graph = pd.DataFrame(self.graph_features_list)
            output_path = self.output_dir / 'graph_features.csv'
            df_graph.to_csv(output_path, index=False)
            logger.info(f"Saved {len(df_graph)} graph features to {output_path}")
        
        # Save metadata
        if self.metadata_list:
            df_metadata = pd.DataFrame(self.metadata_list)
            output_path = self.output_dir / 'metadata.csv'
            df_metadata.to_csv(output_path, index=False)
            logger.info(f"Saved {len(df_metadata)} metadata entries to {output_path}")
    
    def convert_all(self) -> None:
        """Convert all JSON files in the input directory."""
        json_files = sorted(self.input_dir.glob('*.json'))
        
        if not json_files:
            logger.warning(f"No JSON files found in {self.input_dir}")
            return
        
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        for json_file in json_files:
            self.process_single_file(json_file)
        
        self.save_csv_files()
        
        # Print summary statistics
        self.print_summary()
    
    def print_summary(self) -> None:
        """Print summary statistics of the conversion."""
        logger.info("\n" + "="*60)
        logger.info("CONVERSION SUMMARY")
        logger.info("="*60)
        
        if self.metadata_list:
            df_meta = pd.DataFrame(self.metadata_list)
            total_snapshots = len(df_meta)
            normal_count = len(df_meta[df_meta['scenario_type'] == 'normal'])
            stress_count = len(df_meta[df_meta['scenario_type'] == 'stress'])
            
            logger.info(f"Total snapshots processed: {total_snapshots}")
            logger.info(f"Normal scenarios: {normal_count} ({normal_count/total_snapshots*100:.1f}%)")
            logger.info(f"Stress scenarios: {stress_count} ({stress_count/total_snapshots*100:.1f}%)")
        
        if self.node_features_list:
            logger.info(f"Total node features: {len(self.node_features_list)}")
        
        if self.edge_features_list:
            logger.info(f"Total edges: {len(self.edge_features_list)}")
        
        if self.graph_features_list:
            df_graph = pd.DataFrame(self.graph_features_list)
            logger.info(f"\nGraph-level statistics:")
            logger.info(f"  Avg pods per snapshot: {df_graph['total_pods'].mean():.1f}")
            logger.info(f"  Avg nodes per snapshot: {df_graph['total_nodes'].mean():.1f}")
            logger.info(f"  Avg CPU usage: {df_graph['avg_pod_cpu'].mean():.4f}")
            logger.info(f"  Avg memory (MB): {df_graph['avg_pod_memory_mb'].mean():.1f}")
            logger.info(f"  Avg API latency (ms): {df_graph['avg_api_latency_ms'].mean():.2f}")
        
        logger.info("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Convert K8s JSON snapshots to CSV format for GNN training'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default='data/raw',
        help='Input directory containing JSON files (default: data/raw)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/processed',
        help='Output directory for CSV files (default: data/processed)'
    )
    
    args = parser.parse_args()
    
    # Create converter and process files
    converter = JSONToCSVConverter(args.input_dir, args.output_dir)
    converter.convert_all()
    
    logger.info("Conversion complete!")


if __name__ == '__main__':
    main()

# Made with Bob
