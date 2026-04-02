"""
Dataset and Data Loading utilities for K8s Failure Prediction GNN

This module handles loading CSV data and converting it to PyTorch Geometric graph format.
"""

import pandas as pd
import numpy as np
import torch
from torch_geometric.data import Data, Dataset
from torch.utils.data import DataLoader
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from sklearn.preprocessing import StandardScaler, LabelEncoder
import pickle


class K8sGraphDataset(Dataset):
    """
    PyTorch Geometric Dataset for Kubernetes cluster graphs.
    Loads data from CSV files and converts to graph format.
    """
    
    def __init__(
        self,
        data_dir: str = 'data/processed',
        snapshot_ids: Optional[List[str]] = None,
        transform=None,
        pre_transform=None,
        normalize: bool = True,
        cache_dir: Optional[str] = None
    ):
        """
        Args:
            data_dir: Directory containing CSV files
            snapshot_ids: List of snapshot IDs to include (None = all)
            transform: Optional transform to apply to each graph
            pre_transform: Optional pre-transform to apply once
            normalize: Whether to normalize node features
            cache_dir: Directory to cache processed graphs
        """
        self.data_dir = Path(data_dir)
        self.normalize = normalize
        self.cache_dir = Path(cache_dir) if cache_dir else self.data_dir / 'cache'
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load CSV files
        self.metadata = pd.read_csv(self.data_dir / 'metadata.csv')
        self.node_features = pd.read_csv(self.data_dir / 'node_features.csv')
        self.edge_features = pd.read_csv(self.data_dir / 'edge_features.csv')
        self.graph_features = pd.read_csv(self.data_dir / 'graph_features.csv')
        
        # Filter by snapshot_ids if provided
        if snapshot_ids is not None:
            self.metadata = self.metadata[self.metadata['snapshot_id'].isin(snapshot_ids)]
        
        self.snapshot_ids = self.metadata['snapshot_id'].unique().tolist()
        
        # Initialize scalers
        self.node_scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        
        # Fit scalers on training data
        if normalize:
            self._fit_scalers()
        
        super(K8sGraphDataset, self).__init__(str(self.data_dir), transform, pre_transform)
    
    def _fit_scalers(self):
        """Fit scalers on node features."""
        # Select numeric columns for normalization
        numeric_cols = ['cpu_usage', 'memory_usage_mb', 'restart_count']
        
        # Get all node features for fitting
        node_data = self.node_features[numeric_cols].values
        self.node_scaler.fit(node_data)
        
        # Fit label encoder
        labels = self.metadata['label'].values
        self.label_encoder.fit(labels)
    
    def len(self) -> int:
        """Return the number of graphs in the dataset."""
        return len(self.snapshot_ids)
    
    def get(self, idx: int) -> Data:
        """
        Get a single graph by index.
        
        Args:
            idx: Index of the graph
        
        Returns:
            data: PyTorch Geometric Data object
        """
        snapshot_id = self.snapshot_ids[idx]
        
        # Check cache
        cache_file = self.cache_dir / f'graph_{snapshot_id}.pt'
        if cache_file.exists():
            return torch.load(cache_file)
        
        # Get data for this snapshot
        nodes = self.node_features[self.node_features['snapshot_id'] == snapshot_id].copy()
        edges = self.edge_features[self.edge_features['snapshot_id'] == snapshot_id].copy()
        meta = self.metadata[self.metadata['snapshot_id'] == snapshot_id].iloc[0]
        
        # Create node ID mapping
        node_ids = nodes['node_id'].unique()
        node_id_map = {node_id: i for i, node_id in enumerate(node_ids)}
        
        # Extract node features
        node_features = self._extract_node_features(nodes)
        
        # Extract edges
        edge_index = self._extract_edges(edges, node_id_map)
        
        # Get label
        label = self._get_label(meta)
        
        # Create PyG Data object
        data = Data(
            x=node_features,
            edge_index=edge_index,
            y=label,
            snapshot_id=snapshot_id
        )
        
        # Cache the graph
        torch.save(data, cache_file)
        
        return data
    
    def _extract_node_features(self, nodes: pd.DataFrame) -> torch.Tensor:
        """
        Extract and normalize node features.
        
        Args:
            nodes: DataFrame with node data
        
        Returns:
            features: Tensor of shape (num_nodes, num_features)
        """
        # Numeric features
        numeric_cols = ['cpu_usage', 'memory_usage_mb', 'restart_count']
        numeric_features = nodes[numeric_cols].values
        
        # Normalize if enabled
        if self.normalize:
            numeric_features = self.node_scaler.transform(numeric_features)
        
        # Categorical features (one-hot encoding)
        node_type = pd.get_dummies(nodes['node_type'], prefix='type').values
        status = pd.get_dummies(nodes['status'], prefix='status').values
        
        # Combine all features
        features = np.concatenate([
            numeric_features,
            node_type,
            status
        ], axis=1)
        
        return torch.tensor(features, dtype=torch.float)
    
    def _extract_edges(self, edges: pd.DataFrame, node_id_map: Dict) -> torch.Tensor:
        """
        Extract edge indices.
        
        Args:
            edges: DataFrame with edge data
            node_id_map: Mapping from node_id to index
        
        Returns:
            edge_index: Tensor of shape (2, num_edges)
        """
        if len(edges) == 0:
            # Return empty edge index if no edges
            return torch.zeros((2, 0), dtype=torch.long)
        
        # Map node IDs to indices
        source_indices = edges['source_node'].map(node_id_map).values
        target_indices = edges['target_node'].map(node_id_map).values
        
        # Create edge index (bidirectional)
        edge_index = np.array([
            np.concatenate([source_indices, target_indices]),
            np.concatenate([target_indices, source_indices])
        ])
        
        return torch.tensor(edge_index, dtype=torch.long)
    
    def _get_label(self, meta: pd.Series) -> torch.Tensor:
        """
        Get label for the graph.
        
        Args:
            meta: Metadata series
        
        Returns:
            label: Tensor with label
        """
        # Convert label to numeric if it's a string
        label = meta['label']
        if isinstance(label, str):
            label = 1 if label == 'pre_failure' else 0
        
        return torch.tensor(label, dtype=torch.long)
    
    def get_class_weights(self) -> torch.Tensor:
        """
        Calculate class weights for handling imbalance.
        
        Returns:
            weights: Tensor of class weights
        """
        labels = []
        for meta in self.metadata.itertuples():
            label = meta.label
            if isinstance(label, str):
                label = 1 if label == 'pre_failure' else 0
            labels.append(label)
        
        labels = np.array(labels)
        class_counts = np.bincount(labels)
        total = len(labels)
        weights = total / (len(class_counts) * class_counts)
        
        return torch.tensor(weights, dtype=torch.float)
    
    def save_scalers(self, path: str):
        """Save fitted scalers to disk."""
        scalers = {
            'node_scaler': self.node_scaler,
            'label_encoder': self.label_encoder
        }
        with open(path, 'wb') as f:
            pickle.dump(scalers, f)
    
    def load_scalers(self, path: str):
        """Load fitted scalers from disk."""
        with open(path, 'rb') as f:
            scalers = pickle.load(f)
        self.node_scaler = scalers['node_scaler']
        self.label_encoder = scalers['label_encoder']


def create_dataloaders(
    data_dir: str = 'data/processed',
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    batch_size: int = 32,
    shuffle: bool = True,
    random_seed: int = 42
) -> Tuple[DataLoader, DataLoader, DataLoader, K8sGraphDataset]:
    """
    Create train, validation, and test dataloaders.
    
    Args:
        data_dir: Directory containing CSV files
        train_ratio: Ratio of data for training
        val_ratio: Ratio of data for validation
        test_ratio: Ratio of data for testing
        batch_size: Batch size for dataloaders
        shuffle: Whether to shuffle training data
        random_seed: Random seed for reproducibility
    
    Returns:
        train_loader: Training dataloader
        val_loader: Validation dataloader
        test_loader: Test dataloader
        full_dataset: Full dataset (for accessing scalers)
    """
    # Load metadata to get snapshot IDs
    metadata = pd.read_csv(Path(data_dir) / 'metadata.csv')
    
    # Stratified split by label
    from sklearn.model_selection import train_test_split
    
    snapshot_ids = metadata['snapshot_id'].values
    labels = metadata['label'].values
    
    # Convert string labels to numeric for stratification
    numeric_labels = []
    for label in labels:
        if isinstance(label, str):
            numeric_labels.append(1 if label == 'pre_failure' else 0)
        else:
            numeric_labels.append(label)
    
    # First split: train + val vs test
    train_val_ids, test_ids = train_test_split(
        snapshot_ids,
        test_size=test_ratio,
        stratify=numeric_labels,
        random_state=random_seed
    )
    
    # Get labels for train+val split
    train_val_labels = [numeric_labels[i] for i in range(len(snapshot_ids)) 
                        if snapshot_ids[i] in train_val_ids]
    
    # Second split: train vs val
    val_size = val_ratio / (train_ratio + val_ratio)
    train_ids, val_ids = train_test_split(
        train_val_ids,
        test_size=val_size,
        stratify=train_val_labels,
        random_state=random_seed
    )
    
    # Create datasets
    train_dataset = K8sGraphDataset(data_dir, snapshot_ids=train_ids.tolist())
    val_dataset = K8sGraphDataset(data_dir, snapshot_ids=val_ids.tolist())
    test_dataset = K8sGraphDataset(data_dir, snapshot_ids=test_ids.tolist())
    
    # Share scalers across datasets
    val_dataset.node_scaler = train_dataset.node_scaler
    val_dataset.label_encoder = train_dataset.label_encoder
    test_dataset.node_scaler = train_dataset.node_scaler
    test_dataset.label_encoder = train_dataset.label_encoder
    
    # Create dataloaders
    from torch_geometric.loader import DataLoader as PyGDataLoader
    
    train_loader = PyGDataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=shuffle
    )
    
    val_loader = PyGDataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False
    )
    
    test_loader = PyGDataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False
    )
    
    print(f"Dataset splits:")
    print(f"  Train: {len(train_dataset)} graphs")
    print(f"  Val: {len(val_dataset)} graphs")
    print(f"  Test: {len(test_dataset)} graphs")
    
    return train_loader, val_loader, test_loader, train_dataset


if __name__ == '__main__':
    # Example usage
    print("Loading K8s graph dataset...")
    
    # Create dataloaders
    train_loader, val_loader, test_loader, dataset = create_dataloaders(
        data_dir='data/processed',
        batch_size=32
    )
    
    # Get a batch
    batch = next(iter(train_loader))
    print(f"\nBatch info:")
    print(f"  Num graphs: {batch.num_graphs}")
    print(f"  Num nodes: {batch.num_nodes}")
    print(f"  Num edges: {batch.num_edges}")
    print(f"  Node features shape: {batch.x.shape}")
    print(f"  Labels: {batch.y}")
    
    # Get class weights
    weights = dataset.get_class_weights()
    print(f"\nClass weights: {weights}")

# Made with Bob
