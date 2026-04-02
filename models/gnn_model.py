"""
Graph Neural Network Model for Kubernetes Failure Prediction

This module implements a GNN-based model for predicting failures in Kubernetes clusters
by analyzing the cluster topology and resource metrics as a graph structure.

Architecture:
- Graph Attention Networks (GAT) for learning node representations
- Temporal attention for capturing time-series patterns
- Graph-level classification for failure prediction
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, global_mean_pool, global_max_pool
from torch_geometric.data import Data, Batch
from typing import Optional, Tuple


class TemporalAttention(nn.Module):
    """
    Temporal attention mechanism for capturing time-series patterns.
    Learns to focus on important time steps in the sequence.
    """
    
    def __init__(self, hidden_dim: int):
        super(TemporalAttention, self).__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Tensor of shape (batch_size, seq_len, hidden_dim)
        
        Returns:
            context: Weighted sum of inputs (batch_size, hidden_dim)
            attention_weights: Attention scores (batch_size, seq_len)
        """
        # Calculate attention scores
        attention_scores = self.attention(x)  # (batch_size, seq_len, 1)
        attention_weights = F.softmax(attention_scores, dim=1)  # (batch_size, seq_len, 1)
        
        # Apply attention weights
        context = torch.sum(attention_weights * x, dim=1)  # (batch_size, hidden_dim)
        
        return context, attention_weights.squeeze(-1)


class GATLayer(nn.Module):
    """
    Graph Attention Layer with residual connections and layer normalization.
    """
    
    def __init__(self, in_channels: int, out_channels: int, heads: int = 4, dropout: float = 0.3):
        super(GATLayer, self).__init__()
        self.gat = GATConv(in_channels, out_channels, heads=heads, dropout=dropout, concat=True)
        self.norm = nn.LayerNorm(out_channels * heads)
        self.dropout = nn.Dropout(dropout)
        
        # Residual connection projection if dimensions don't match
        self.residual_proj = None
        if in_channels != out_channels * heads:
            self.residual_proj = nn.Linear(in_channels, out_channels * heads)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Node features (num_nodes, in_channels)
            edge_index: Edge indices (2, num_edges)
        
        Returns:
            Updated node features (num_nodes, out_channels * heads)
        """
        identity = x
        
        # Apply GAT
        x = self.gat(x, edge_index)
        x = self.dropout(x)
        
        # Residual connection
        if self.residual_proj is not None:
            identity = self.residual_proj(identity)
        x = x + identity
        
        # Layer normalization
        x = self.norm(x)
        x = F.elu(x)
        
        return x


class K8sFailurePredictionGNN(nn.Module):
    """
    Complete GNN model for Kubernetes failure prediction.
    
    Architecture:
    1. Node feature encoding
    2. Multiple GAT layers for graph learning
    3. Graph-level pooling (mean + max)
    4. Temporal attention (if using sequences)
    5. Classification head
    """
    
    def __init__(
        self,
        node_feature_dim: int = 11,  # From node_features.csv
        hidden_dim: int = 128,
        num_gat_layers: int = 3,
        num_heads: int = 4,
        num_classes: int = 2,  # Binary: normal vs pre-failure
        dropout: float = 0.3,
        use_temporal: bool = False,
        seq_length: int = 5
    ):
        """
        Args:
            node_feature_dim: Dimension of input node features
            hidden_dim: Hidden dimension for GAT layers
            num_gat_layers: Number of GAT layers
            num_heads: Number of attention heads in GAT
            num_classes: Number of output classes
            dropout: Dropout rate
            use_temporal: Whether to use temporal attention
            seq_length: Length of temporal sequences (if use_temporal=True)
        """
        super(K8sFailurePredictionGNN, self).__init__()
        
        self.use_temporal = use_temporal
        self.seq_length = seq_length
        
        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(node_feature_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ELU(),
            nn.Dropout(dropout)
        )
        
        # GAT layers
        self.gat_layers = nn.ModuleList()
        current_dim = hidden_dim
        
        for i in range(num_gat_layers):
            out_dim = hidden_dim // num_heads  # Ensure output is hidden_dim after concat
            self.gat_layers.append(
                GATLayer(current_dim, out_dim, heads=num_heads, dropout=dropout)
            )
            current_dim = out_dim * num_heads
        
        # Graph-level pooling dimension
        graph_dim = current_dim * 2  # mean + max pooling
        
        # Temporal attention (if enabled)
        if use_temporal:
            self.temporal_attention = TemporalAttention(graph_dim)
            final_dim = graph_dim
        else:
            final_dim = graph_dim
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(final_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_classes)
        )
    
    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        batch: torch.Tensor,
        return_attention: bool = False
    ) -> torch.Tensor:
        """
        Forward pass through the model.
        
        Args:
            x: Node features (num_nodes, node_feature_dim)
            edge_index: Edge indices (2, num_edges)
            batch: Batch assignment for nodes (num_nodes,)
            return_attention: Whether to return attention weights
        
        Returns:
            logits: Class logits (batch_size, num_classes)
            attention_weights: (Optional) Attention weights if return_attention=True
        """
        # Input projection
        x = self.input_proj(x)
        
        # Apply GAT layers
        for gat_layer in self.gat_layers:
            x = gat_layer(x, edge_index)
        
        # Graph-level pooling
        x_mean = global_mean_pool(x, batch)
        x_max = global_max_pool(x, batch)
        x_graph = torch.cat([x_mean, x_max], dim=1)
        
        # Temporal attention (if enabled)
        attention_weights = None
        if self.use_temporal:
            # Reshape for temporal processing
            batch_size = x_graph.size(0) // self.seq_length
            x_graph = x_graph.view(batch_size, self.seq_length, -1)
            x_graph, attention_weights = self.temporal_attention(x_graph)
        
        # Classification
        logits = self.classifier(x_graph)
        
        if return_attention and attention_weights is not None:
            return logits, attention_weights
        return logits
    
    def predict(self, x: torch.Tensor, edge_index: torch.Tensor, batch: torch.Tensor) -> torch.Tensor:
        """
        Make predictions (returns class probabilities).
        
        Args:
            x: Node features
            edge_index: Edge indices
            batch: Batch assignment
        
        Returns:
            probs: Class probabilities (batch_size, num_classes)
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(x, edge_index, batch)
            probs = F.softmax(logits, dim=1)
        return probs
    
    def get_embeddings(self, x: torch.Tensor, edge_index: torch.Tensor, batch: torch.Tensor) -> torch.Tensor:
        """
        Extract graph embeddings (before classification head).
        
        Args:
            x: Node features
            edge_index: Edge indices
            batch: Batch assignment
        
        Returns:
            embeddings: Graph embeddings (batch_size, embedding_dim)
        """
        self.eval()
        with torch.no_grad():
            # Input projection
            x = self.input_proj(x)
            
            # Apply GAT layers
            for gat_layer in self.gat_layers:
                x = gat_layer(x, edge_index)
            
            # Graph-level pooling
            x_mean = global_mean_pool(x, batch)
            x_max = global_max_pool(x, batch)
            embeddings = torch.cat([x_mean, x_max], dim=1)
            
            # Temporal attention (if enabled)
            if self.use_temporal:
                batch_size = embeddings.size(0) // self.seq_length
                embeddings = embeddings.view(batch_size, self.seq_length, -1)
                embeddings, _ = self.temporal_attention(embeddings)
        
        return embeddings


class FocalLoss(nn.Module):
    """
    Focal Loss for handling class imbalance.
    Focuses training on hard examples.
    """
    
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        """
        Args:
            alpha: Weighting factor for class balance
            gamma: Focusing parameter (higher = more focus on hard examples)
        """
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            inputs: Model predictions (batch_size, num_classes)
            targets: Ground truth labels (batch_size,)
        
        Returns:
            loss: Focal loss value
        """
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-ce_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * ce_loss
        return focal_loss.mean()


def create_model(config: dict) -> K8sFailurePredictionGNN:
    """
    Factory function to create model from configuration.
    
    Args:
        config: Dictionary with model configuration
    
    Returns:
        model: Initialized GNN model
    """
    return K8sFailurePredictionGNN(
        node_feature_dim=config.get('node_feature_dim', 11),
        hidden_dim=config.get('hidden_dim', 128),
        num_gat_layers=config.get('num_gat_layers', 3),
        num_heads=config.get('num_heads', 4),
        num_classes=config.get('num_classes', 2),
        dropout=config.get('dropout', 0.3),
        use_temporal=config.get('use_temporal', False),
        seq_length=config.get('seq_length', 5)
    )


if __name__ == '__main__':
    # Example usage
    print("Creating K8s Failure Prediction GNN model...")
    
    # Model configuration
    config = {
        'node_feature_dim': 11,
        'hidden_dim': 128,
        'num_gat_layers': 3,
        'num_heads': 4,
        'num_classes': 2,
        'dropout': 0.3,
        'use_temporal': False
    }
    
    # Create model
    model = create_model(config)
    print(f"Model created with {sum(p.numel() for p in model.parameters())} parameters")
    
    # Example forward pass
    num_nodes = 10
    num_edges = 15
    batch_size = 2
    
    x = torch.randn(num_nodes, 11)  # Node features
    edge_index = torch.randint(0, num_nodes, (2, num_edges))  # Edge indices
    batch = torch.tensor([0] * 5 + [1] * 5)  # Batch assignment
    
    # Forward pass
    logits = model(x, edge_index, batch)
    print(f"Output shape: {logits.shape}")  # Should be (2, 2)
    
    # Predictions
    probs = model.predict(x, edge_index, batch)
    print(f"Predictions: {probs}")

# Made with Bob
