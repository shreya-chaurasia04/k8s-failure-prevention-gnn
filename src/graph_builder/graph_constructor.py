import networkx as nx
import json
import numpy as np
from datetime import datetime

class GraphConstructor:
    def __init__(self):
        self.G = None
    
    def build_from_snapshot(self, snapshot_path):
        with open(snapshot_path, 'r') as f:
            data = json.load(f)
        
        # Create heterogeneous graph
        self.G = nx.DiGraph()
        
        # Add nodes
        self._add_pod_nodes(data)
        self._add_node_nodes(data)
        
        # Add edges
        self._add_pod_to_node_edges(data)
        
        return self.G
    
    def _add_pod_nodes(self, data):
        pods = data['topology']['pods']
        metrics = data['metrics']
        
        for pod in pods:
            # Extract CPU/memory from metrics
            cpu = self._get_pod_metric(metrics['pod_cpu'], pod['name'])
            memory = self._get_pod_metric(metrics['pod_memory'], pod['name'])
            
            self.G.add_node(
                pod['name'],
                type='pod',
                namespace=pod['namespace'],
                status=pod['status'],
                cpu=cpu,
                memory=memory
            )
    
    def _add_node_nodes(self, data):
        nodes = data['topology']['nodes']
        node_cpu = data['metrics']['node_cpu']
        node_mem = data['metrics']['node_memory']
        
        for node in nodes:
            cpu = self._get_node_metric(node_cpu, node['name'])
            mem = self._get_node_metric(node_mem, node['name'])
            
            self.G.add_node(
                node['name'],
                type='node',
                cpu=cpu,
                memory=mem
            )
    
    def _add_pod_to_node_edges(self, data):
        for pod in data['topology']['pods']:
            if pod['node']:
                self.G.add_edge(
                    pod['name'],
                    pod['node'],
                    type='runs_on'
                )
    
    def _get_pod_metric(self, metric_results, pod_name):
        for result in metric_results:
            if result['metric'].get('pod') == pod_name:
                return float(result['value'][1])
        return 0.0
    
    def _get_node_metric(self, metric_results, node_name):
        for result in metric_results:
            instance = result['metric'].get('instance', '')
            if node_name in instance:
                return float(result['value'][1])
        return 0.0
    
    def get_features(self):
        features = {}
        for node in self.G.nodes():
            attrs = self.G.nodes[node]
            features[node] = {
                'type': attrs['type'],
                'cpu': attrs.get('cpu', 0),
                'memory': attrs.get('memory', 0)
            }
        return features