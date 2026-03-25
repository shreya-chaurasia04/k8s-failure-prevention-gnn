import torch
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from torch_geometric.data import Data

class ClusterGraphArchitect:
    def __init__(self):
        # define Categories, not specific Pod IDs
        # This keeps the graph stable even if pods restart with new names
        self.node_categories = [
            'control-plane', 'worker', 'worker2', 'worker3', # The Physical Nodes
            'apiserver', 'etcd',                            # The Control Plane
            'frontend', 'backend', 'redis'                  # The Data Plane
        ]
        self.name_to_id = {name: i for i, name in enumerate(self.node_categories)}
        self.id_to_name = {i: name for name, i in self.name_to_id.items()}

    def build_topology(self):
        # building the adj matrix for nodes based on the logical and physical relationships in the cluster  
        edges = [
            # Logical Flow (Traffic goes both ways: Request & Response)
            ['frontend', 'backend'], ['backend', 'frontend'],
            ['backend', 'redis'], ['redis', 'backend'],
            
            # Physical Hosting (Shared Fate)
            ['frontend', 'worker'], ['worker', 'frontend'],
            ['backend', 'worker'], ['worker', 'backend'],
            ['redis', 'worker'], ['worker', 'redis'],
            
            # Control Plane (Orchestration)
            ['etcd', 'apiserver'], ['apiserver', 'etcd'],
            ['apiserver', 'frontend'], ['frontend', 'apiserver']
        ]
        # Convert to Tensors with Node IDs instead of Names
        int_edges = [[self.name_to_id[s], self.name_to_id[t]] for s, t in edges]
        return torch.tensor(int_edges, dtype=torch.long).t().contiguous()

    def create_graph(self, csv_path):
        df = pd.read_csv(csv_path)
        graphs = []

        for ts, group in df.groupby('timestamp'):
            # Feature Matrix [NumNodes, 3 Features]
            # Features: [api_rate, etcd_fsync, pod_cpu]
            x = torch.zeros((len(self.node_categories), 3), dtype=torch.float)
            
            for _, row in group.iterrows():
                # Map the raw entity name (like 'frontend-xyz') to our category
                category = self._find_category(row['entity'])
                if category:
                    node_id = self.name_to_id[category]
                    # Update features (taking max if multiple pods match one category)
                    val_vec = torch.tensor([row['api_rate'], row['etcd_fsync'], row['pod_cpu']])
                    x[node_id] = torch.max(x[node_id], val_vec)

            edge_index = self.build_topology()
            y = torch.tensor([group['label'].iloc[0]], dtype=torch.long)
            
            graphs.append(Data(x=x, edge_index=edge_index, y=y, timestamp=ts))
        return graphs

    def _find_category(self, entity):
        for cat in self.node_categories:
            if cat in entity: return cat
        if '172.18.0.2' in entity: return 'etcd'
        if 'cluster' in entity: return 'apiserver'
        return None

    def visualize(self, data):
        G = nx.DiGraph()
        
        # CRITICAL: Add ALL categories as nodes first so the count matches
        G.add_nodes_from(self.node_categories)

        # Tier 0: The Nodes (Bottom) | Tier 1: The Control Plane (Middle) | Tier 2: The Apps (Top)
        layers = {
            'worker': 0, 'worker2': 0, 'worker3': 0, 'control-plane': 0,
            'etcd': 1, 'apiserver': 1,
            'frontend': 2, 'backend': 2, 'redis': 2
        }
        
        edge_index = data.edge_index.tolist()
        for i in range(len(edge_index[0])):
            src, dst = edge_index[0][i], edge_index[1][i]
            G.add_edge(self.id_to_name[src], self.id_to_name[dst])

        # Coordinate mapping: (x=Layer, y=Position in Layer)
        pos = {}
        layer_counts = {0: 0, 1: 0, 2: 0}
        for node, layer in layers.items():
            # Space out nodes vertically within their horizontal tier
            pos[node] = (layer * 3, -layer_counts[layer] * 1.5)
            layer_counts[layer] += 1

        # Now colors (9) will match nodes (9)
        colors = []
        for i in range(len(self.node_categories)):
            if data.x[i][1] > 0.05: colors.append('red') 
            elif data.x[i][2] > 0.01: colors.append('orange') 
            else: colors.append('skyblue')

        plt.figure(figsize=(12, 7), facecolor='#dfe6e9')
        nx.draw(G, pos, with_labels=True, node_color=colors, node_size=4500, font_size=10, font_weight='bold', edge_color='#636e72', width=2, arrowsize=25, connectionstyle="arc3,rad=0.1")
        plt.title(f"GNN Research: Cluster Topology\nLabel: {'FAILURE' if data.y.item()==1 else 'HEALTHY'}", fontsize=14)
        plt.show()

if __name__ == "__main__":
    arch = ClusterGraphArchitect()
    # Test it on your latest Failure CSV
    graphs = arch.create_graph("/root/K8-Project/structure/data/failure/etcd_failure_batch_7.csv")
    arch.visualize(graphs[0])