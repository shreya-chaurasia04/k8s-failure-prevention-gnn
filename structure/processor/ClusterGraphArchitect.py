import torch
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from torch_geometric.data import Data

class ClusterGraphArchitect:
    def __init__(self):
        # Stable categories for GNN input/output layers
        self.node_categories = [
            'control-plane', 'worker', 'worker2', 'worker3', 
            'apiserver', 'etcd', 
            'frontend', 'backend', 'redis'
        ]
        self.name_to_id = {name: i for i, name in enumerate(self.node_categories)}
        self.id_to_name = {i: name for name, i in self.name_to_id.items()}

    def _find_category(self, name):
        """Maps raw string names (pods/nodes/IPs) to stable categories."""
        if not name or pd.isna(name) or name == 'n/a': 
            return None
        
        name = str(name).lower()
        
        # Priority mapping
        if 'apiserver' in name or 'cluster' in name: return 'apiserver'
        if 'etcd' in name or '172.18' in name: return 'etcd'
        if 'control-plane' in name: return 'control-plane'
        
        # Workload mapping
        for cat in ['frontend', 'backend', 'redis']:
            if cat in name: return cat
            
        # Worker mapping (handles 'gnn-research-worker2' -> 'worker2')
        if 'worker' in name:
            if 'worker2' in name: return 'worker2'
            if 'worker3' in name: return 'worker3'
            return 'worker'
            
        return None

    def _get_static_logical_edges(self):
        """Logical flow and static Control Plane dependencies."""
        return [
            ['frontend', 'backend'], 
            ['backend', 'redis'],
            ['apiserver', 'etcd'],
            ['apiserver', 'control-plane']
        ]

    def create_graph(self, csv_path):
        df = pd.read_csv(csv_path)
        graphs = []

        for ts, group in df.groupby('timestamp'):
            # Feature Matrix [NumNodes, 4 Features]
            x = torch.zeros((len(self.node_categories), 4), dtype=torch.float)
            
            # Start with logical edges for this specific snapshot
            current_edges = self._get_static_logical_edges()
            
            # Use unique nodes in this snapshot to link APIServer to all active Workers
            active_nodes = group['node'].unique()
            for raw_node in active_nodes:
                node_cat = self._find_category(raw_node)
                if node_cat and 'worker' in node_cat:
                    current_edges.append(['apiserver', node_cat])

            for _, row in group.iterrows():
                pod_cat = self._find_category(row['entity'])
                node_cat = self._find_category(row['node'])
                
                if pod_cat:
                    node_id = self.name_to_id[pod_cat]
                    val_vec = torch.tensor([
                        row.get('api_rate', 0), row.get('etcd_fsync', 0),
                        row.get('pod_cpu', 0), row.get('api_latency', 0)
                    ], dtype=torch.float)
                    
                    # Use max to aggregate metrics if multiple pods map to one category
                    x[node_id] = torch.max(x[node_id], val_vec)

                    # 2. DYNAMIC PHYSICAL EDGES: Link Pod to its host Node
                    if node_cat and pod_cat != node_cat:
                        current_edges.append([pod_cat, node_cat])

            # Convert name-based edges to bidirectional ID-based tensor
            edge_index = self._build_edge_index(current_edges)
            
            # Diagnosis Labels: 0=Healthy, 1=Etcd, 2=API
            y = torch.tensor([group['label'].iloc[0]], dtype=torch.long)
            
            graphs.append(Data(x=x, edge_index=edge_index, y=y, timestamp=ts))
            
        return graphs

    def _build_edge_index(self, edge_list):
        """Converts category names to ID pairs and ensures bidirectional flow."""
        indices = []
        for s, t in edge_list:
            if s in self.name_to_id and t in self.name_to_id:
                u, v = self.name_to_id[s], self.name_to_id[t]
                indices.append([u, v])
                indices.append([v, u]) # GNN message passing is usually bidirectional
        return torch.tensor(indices, dtype=torch.long).t().contiguous()

    def visualize(self, data):
        G = nx.DiGraph()
        G.add_nodes_from(self.node_categories)
        
        # Visualization Tiers
        layers = {
            'control-plane': 0, 'worker': 0, 'worker2': 0, 'worker3': 0,
            'etcd': 1, 'apiserver': 1,
            'frontend': 2, 'backend': 2, 'redis': 2
        }
        
        # Reconstruct edges for NetworkX from the edge_index tensor
        edge_list = data.edge_index.t().tolist()
        for src, dst in edge_list:
            G.add_edge(self.id_to_name[src], self.id_to_name[dst])

        pos = {}
        layer_counts = {0: 0, 1: 0, 2: 0}
        for node, layer in layers.items():
            pos[node] = (layer * 4, -layer_counts[layer] * 2)
            layer_counts[layer] += 1

        # Dynamic Color Logic based on Feature Activation
        colors = []
        for i in range(len(self.node_categories)):
            feat = data.x[i]
            if feat[1] > 0.05: colors.append('#ff4d4d')    # Etcd Stress (Red)
            elif feat[3] > 0.1: colors.append('#9b59b6')   # API Latency (Purple)
            elif feat[2] > 0.5: colors.append('#e67e22')   # Workload CPU (Orange)
            else: colors.append('#4db8ff')                # Healthy (Blue)

        plt.figure(figsize=(14, 8), facecolor='#f5f6fa')
        
        status_map = {0: "HEALTHY", 1: "ETCD FAILURE", 2: "API SATURATION"}
        current_status = status_map.get(data.y.item(), "UNKNOWN")
        
        nx.draw(G, pos, with_labels=True, node_color=colors, node_size=5000, 
                font_size=9, font_weight='bold', edge_color='#b2bec3', 
                width=1.2, arrowsize=15, connectionstyle="arc3,rad=0.05")
        
        plt.title(f"Dynamic GNN Topology\nDetected State: {current_status}", 
                  fontsize=16, fontweight='bold')
        plt.show()

if __name__ == "__main__":
    arch = ClusterGraphArchitect()
    graphs = arch.create_graph("/root/K8-Project/structure/data/failure/etcd_failure_batch_10.csv")
    arch.visualize(graphs[0])