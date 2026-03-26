import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GINConv, global_mean_pool

class GNNStack(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers):
        super(GNNStack, self).__init__()
        self.num_layers = num_layers
        self.convs = nn.ModuleList()
        self.batch_norms = nn.ModuleList()

        # Build GIN Layers
        for i in range(num_layers):
            start_dim = input_dim if i == 0 else hidden_dim
            
            # GIN requires an internal MLP for the epsilon mapping
            # This is what makes it mathematically powerful for graph isomorphism
            mlp = nn.Sequential(
                nn.Linear(start_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim)
            )
            
            self.convs.append(GINConv(mlp))
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim))

        # Post-Message Passing: The Classifier
        # This takes the pooled graph embedding and turns it into Healthy/Failure logits
        self.post_mp = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3), # Regularization for your RTX 5060 to prevent overfitting
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch

        # 1. Message Passing Layers
        for i in range(self.num_layers):
            x = self.convs[i](x, edge_index)
            x = self.batch_norms[i](x)
            x = F.relu(x)

        # 2. Readout Layer (Global Pooling)
        # Collapses all node features into one "Graph Signature" vector
        x = global_mean_pool(x, batch)

        # 3. Final Classification
        return self.post_mp(x)