"""
Inference module for K8s Failure Prediction GNN

This module provides real-time inference capabilities for the trained model.
"""

import torch
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
import pickle
from datetime import datetime

from gnn_model import K8sFailurePredictionGNN, create_model
from dataset import K8sGraphDataset


class FailurePredictor:
    """
    Real-time failure predictor for Kubernetes clusters.
    Loads trained model and makes predictions on new data.
    """
    
    def __init__(
        self,
        model_path: str = 'outputs/best_model.pt',
        scalers_path: str = 'outputs/scalers.pkl',
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        """
        Args:
            model_path: Path to trained model checkpoint
            scalers_path: Path to fitted scalers
            device: Device to run inference on
        """
        self.device = device
        
        # Load checkpoint
        print(f"Loading model from {model_path}...")
        checkpoint = torch.load(model_path, map_location=device)
        
        # Create model
        config = checkpoint['config']
        self.model = create_model(config)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(device)
        self.model.eval()
        
        # Load scalers
        print(f"Loading scalers from {scalers_path}...")
        with open(scalers_path, 'rb') as f:
            scalers = pickle.load(f)
        self.node_scaler = scalers['node_scaler']
        self.label_encoder = scalers['label_encoder']
        
        print("Model loaded successfully!")
        print(f"Running on: {device}")
    
    def predict_from_csv(
        self,
        node_features_path: str,
        edge_features_path: str,
        snapshot_id: str
    ) -> Dict:
        """
        Make prediction from CSV files.
        
        Args:
            node_features_path: Path to node features CSV
            edge_features_path: Path to edge features CSV
            snapshot_id: ID of the snapshot to predict
        
        Returns:
            prediction: Dictionary with prediction results
        """
        # Load data
        nodes = pd.read_csv(node_features_path)
        edges = pd.read_csv(edge_features_path)
        
        # Filter by snapshot_id
        nodes = nodes[nodes['snapshot_id'] == snapshot_id]
        edges = edges[edges['snapshot_id'] == snapshot_id]
        
        if len(nodes) == 0:
            raise ValueError(f"No data found for snapshot_id: {snapshot_id}")
        
        # Convert to graph
        graph_data = self._create_graph(nodes, edges)
        
        # Make prediction
        prediction = self.predict(graph_data)
        
        return prediction
    
    def predict_from_snapshot(
        self,
        metrics: Dict,
        topology: Dict
    ) -> Dict:
        """
        Make prediction from raw snapshot data (from collectors).
        
        Args:
            metrics: Metrics dictionary from PrometheusCollector
            topology: Topology dictionary from K8sCollector
        
        Returns:
            prediction: Dictionary with prediction results
        """
        # Convert to DataFrame format
        nodes_df = self._metrics_to_dataframe(metrics, topology)
        edges_df = self._topology_to_edges(topology)
        
        # Create graph
        graph_data = self._create_graph(nodes_df, edges_df)
        
        # Make prediction
        prediction = self.predict(graph_data)
        
        return prediction
    
    def predict(self, graph_data) -> Dict:
        """
        Make prediction on a graph.
        
        Args:
            graph_data: PyTorch Geometric Data object
        
        Returns:
            prediction: Dictionary with prediction results
        """
        with torch.no_grad():
            graph_data = graph_data.to(self.device)
            
            # Forward pass
            logits = self.model(
                graph_data.x,
                graph_data.edge_index,
                graph_data.batch
            )
            
            # Get probabilities
            probs = torch.softmax(logits, dim=1)
            pred_class = logits.argmax(dim=1).item()
            confidence = probs[0, pred_class].item()
            
            # Prepare result
            prediction = {
                'predicted_class': int(pred_class),
                'predicted_label': 'pre_failure' if pred_class == 1 else 'normal',
                'confidence': float(confidence),
                'probabilities': {
                    'normal': float(probs[0, 0]),
                    'pre_failure': float(probs[0, 1])
                },
                'timestamp': datetime.now().isoformat(),
                'risk_level': self._get_risk_level(probs[0, 1].item())
            }
            
            return prediction
    
    def _get_risk_level(self, failure_prob: float) -> str:
        """
        Determine risk level based on failure probability.
        
        Args:
            failure_prob: Probability of failure
        
        Returns:
            risk_level: 'low', 'medium', 'high', or 'critical'
        """
        if failure_prob < 0.3:
            return 'low'
        elif failure_prob < 0.5:
            return 'medium'
        elif failure_prob < 0.7:
            return 'high'
        else:
            return 'critical'
    
    def _create_graph(self, nodes: pd.DataFrame, edges: pd.DataFrame):
        """Create PyTorch Geometric graph from DataFrames."""
        from torch_geometric.data import Data
        
        # Create node ID mapping
        node_ids = nodes['node_id'].unique()
        node_id_map = {node_id: i for i, node_id in enumerate(node_ids)}
        
        # Extract node features
        numeric_cols = ['cpu_usage', 'memory_usage_mb', 'restart_count']
        numeric_features = nodes[numeric_cols].values
        
        # Normalize
        numeric_features = self.node_scaler.transform(numeric_features)
        
        # Categorical features
        node_type = pd.get_dummies(nodes['node_type'], prefix='type').values
        status = pd.get_dummies(nodes['status'], prefix='status').values
        
        # Combine features
        features = np.concatenate([
            numeric_features,
            node_type,
            status
        ], axis=1)
        
        x = torch.tensor(features, dtype=torch.float)
        
        # Extract edges
        if len(edges) > 0:
            source_indices = edges['source_node'].map(node_id_map).values
            target_indices = edges['target_node'].map(node_id_map).values
            
            # Bidirectional edges
            edge_index = np.array([
                np.concatenate([source_indices, target_indices]),
                np.concatenate([target_indices, source_indices])
            ])
            edge_index = torch.tensor(edge_index, dtype=torch.long)
        else:
            edge_index = torch.zeros((2, 0), dtype=torch.long)
        
        # Create batch (single graph)
        batch = torch.zeros(len(nodes), dtype=torch.long)
        
        return Data(x=x, edge_index=edge_index, batch=batch)
    
    def _metrics_to_dataframe(self, metrics: Dict, topology: Dict) -> pd.DataFrame:
        """Convert metrics dictionary to DataFrame format."""
        # This is a simplified version - adjust based on your actual data structure
        nodes_data = []
        
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
            nodes_data.append({
                'snapshot_id': 'current',
                'node_id': pod_name,
                'node_type': 'pod',
                'cpu_usage': pod_cpu.get(pod_name, 0.0),
                'memory_usage_mb': pod_memory.get(pod_name, 0.0) / (1024 * 1024),
                'restart_count': pod_restarts.get(pod_name, 0.0),
                'status': topo_info.get('status', 'Unknown'),
                'namespace': topo_info.get('namespace', 'default'),
                'assigned_node': topo_info.get('node', ''),
                'app_label': topo_info.get('labels', {}).get('app', '')
            })
        
        # Process node metrics
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
            nodes_data.append({
                'snapshot_id': 'current',
                'node_id': node_name,
                'node_type': 'k8s_node',
                'cpu_usage': node_cpu.get(node_name, 0.0),
                'memory_usage_mb': node_memory.get(node_name, 0.0) / (1024 * 1024),
                'restart_count': 0.0,
                'status': 'Ready',
                'namespace': '',
                'assigned_node': '',
                'app_label': ''
            })
        
        return pd.DataFrame(nodes_data)
    
    def _topology_to_edges(self, topology: Dict) -> pd.DataFrame:
        """Convert topology dictionary to edges DataFrame."""
        edges_data = []
        
        for pod in topology.get('pods', []):
            edges_data.append({
                'snapshot_id': 'current',
                'source_node': pod['name'],
                'target_node': pod.get('node', ''),
                'edge_type': 'scheduled_on',
                'weight': 1.0
            })
        
        return pd.DataFrame(edges_data)


def main():
    """Example usage of the predictor."""
    # Initialize predictor
    predictor = FailurePredictor(
        model_path='outputs/best_model.pt',
        scalers_path='outputs/scalers.pkl'
    )
    
    # Example 1: Predict from CSV files
    print("\nExample 1: Prediction from CSV files")
    try:
        prediction = predictor.predict_from_csv(
            node_features_path='data/processed/node_features.csv',
            edge_features_path='data/processed/edge_features.csv',
            snapshot_id='1774286375'  # Replace with actual snapshot ID
        )
        
        print(f"Predicted: {prediction['predicted_label']}")
        print(f"Confidence: {prediction['confidence']:.2%}")
        print(f"Risk Level: {prediction['risk_level']}")
        print(f"Probabilities: {prediction['probabilities']}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Real-time prediction (requires collectors)
    print("\nExample 2: Real-time prediction")
    print("(Requires PrometheusCollector and K8sCollector)")
    print("See src/collectors/ for implementation")


if __name__ == '__main__':
    main()

# Made with Bob
