# GNN Model for Kubernetes Failure Prediction

## Overview

This directory contains a complete Graph Neural Network (GNN) implementation for predicting failures in Kubernetes clusters. The model analyzes cluster topology and resource metrics as a graph structure to detect pre-failure conditions.

---

## Architecture

### Model Components

1. **Graph Attention Networks (GAT)**
   - Multi-head attention mechanism
   - 3 GAT layers with residual connections
   - Layer normalization for stable training

2. **Graph-Level Pooling**
   - Mean and max pooling for graph representation
   - Captures both average and extreme behaviors

3. **Temporal Attention** (Optional)
   - Learns to focus on important time steps
   - Useful for sequence-based predictions

4. **Classification Head**
   - Multi-layer perceptron with dropout
   - Binary classification: Normal vs Pre-Failure

### Key Features

- **Focal Loss**: Handles class imbalance by focusing on hard examples
- **Residual Connections**: Improves gradient flow in deep networks
- **Layer Normalization**: Stabilizes training
- **Dropout**: Prevents overfitting
- **Early Stopping**: Prevents overtraining

---

## Files

```
models/
├── gnn_model.py      # GNN architecture definition
├── dataset.py        # Data loading and preprocessing
├── train.py          # Training script
├── inference.py      # Real-time inference
└── README_GNN_MODEL.md
```

---

## Installation

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies**:
- PyTorch >= 2.0.0
- PyTorch Geometric >= 2.3.0
- pandas, numpy, scikit-learn
- matplotlib (for visualization)

### 3. Install PyTorch Geometric

```bash
# For CUDA 11.8 (adjust based on your CUDA version)
pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.0.0+cu118.html

# For CPU only
pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.0.0+cpu.html
```

---

## Quick Start

### 1. Prepare Data

Ensure you have balanced data (see `README_DATA_COLLECTION.md`):

```bash
# Check current balance
python -c "
import pandas as pd
df = pd.read_csv('data/processed/metadata.csv')
print(df['scenario_type'].value_counts())
"
```

**Required**: ~40-50% normal, 50-60% stress scenarios

### 2. Train Model

```bash
# Activate environment
source venv/bin/activate

# Run training
cd models
python train.py
```

**Training will**:
- Load and split data (70/15/15)
- Train for up to 100 epochs
- Use early stopping (patience=15)
- Save best model to `outputs/best_model.pt`
- Generate training curves and metrics

### 3. Evaluate Model

```bash
# Evaluation runs automatically after training
# Or load and evaluate separately:
python -c "
from train import Trainer, create_model
from dataset import create_dataloaders

# Load data
train_loader, val_loader, test_loader, _ = create_dataloaders()

# Load model
import torch
checkpoint = torch.load('outputs/best_model.pt')
model = create_model(checkpoint['config'])
model.load_state_dict(checkpoint['model_state_dict'])

# Create trainer and evaluate
trainer = Trainer(model, train_loader, val_loader, test_loader, checkpoint['config'])
trainer.evaluate()
"
```

### 4. Make Predictions

```bash
python inference.py
```

---

## Configuration

### Model Hyperparameters

Edit in `train.py` or create a config file:

```python
config = {
    # Model Architecture
    'node_feature_dim': 11,      # Number of node features
    'hidden_dim': 128,           # Hidden layer dimension
    'num_gat_layers': 3,         # Number of GAT layers
    'num_heads': 4,              # Attention heads per layer
    'num_classes': 2,            # Binary classification
    'dropout': 0.3,              # Dropout rate
    
    # Training
    'epochs': 100,
    'batch_size': 32,
    'learning_rate': 0.001,
    'weight_decay': 0.01,
    'grad_clip': 1.0,
    
    # Loss Function
    'use_focal_loss': True,
    'focal_alpha': 0.25,
    'focal_gamma': 2.0,
    
    # Early Stopping
    'early_stopping_patience': 15,
    
    # Data Split
    'train_ratio': 0.7,
    'val_ratio': 0.15,
    'test_ratio': 0.15,
}
```

---

## Model Performance

### Expected Metrics (with balanced data)

| Metric | Target | Good | Excellent |
|--------|--------|------|-----------|
| Accuracy | >85% | >90% | >95% |
| Precision | >80% | >85% | >90% |
| Recall | >80% | >85% | >90% |
| F1 Score | >80% | >85% | >90% |
| ROC-AUC | >0.85 | >0.90 | >0.95 |

### Training Time

- **CPU**: ~30-60 minutes (100 epochs)
- **GPU**: ~5-10 minutes (100 epochs)

### Model Size

- **Parameters**: ~500K-1M
- **Disk Size**: ~5-10 MB
- **Memory**: ~500 MB during training

---

## Usage Examples

### Example 1: Basic Training

```python
from train import main

# Run training with default config
main()
```

### Example 2: Custom Configuration

```python
from train import Trainer, create_model
from dataset import create_dataloaders

# Custom config
config = {
    'hidden_dim': 256,  # Larger model
    'num_gat_layers': 4,
    'learning_rate': 0.0005,
    'epochs': 150
}

# Create dataloaders
train_loader, val_loader, test_loader, _ = create_dataloaders(
    batch_size=config.get('batch_size', 32)
)

# Create and train model
model = create_model(config)
trainer = Trainer(model, train_loader, val_loader, test_loader, config)
trainer.train(epochs=config['epochs'])
```

### Example 3: Real-Time Inference

```python
from inference import FailurePredictor

# Initialize predictor
predictor = FailurePredictor(
    model_path='outputs/best_model.pt',
    scalers_path='outputs/scalers.pkl'
)

# Predict from CSV
prediction = predictor.predict_from_csv(
    node_features_path='data/processed/node_features.csv',
    edge_features_path='data/processed/edge_features.csv',
    snapshot_id='1774286375'
)

print(f"Prediction: {prediction['predicted_label']}")
print(f"Confidence: {prediction['confidence']:.2%}")
print(f"Risk Level: {prediction['risk_level']}")
```

### Example 4: Batch Predictions

```python
from inference import FailurePredictor
import pandas as pd

predictor = FailurePredictor()

# Load metadata
metadata = pd.read_csv('data/processed/metadata.csv')

# Predict on multiple snapshots
results = []
for snapshot_id in metadata['snapshot_id'].head(10):
    try:
        pred = predictor.predict_from_csv(
            'data/processed/node_features.csv',
            'data/processed/edge_features.csv',
            str(snapshot_id)
        )
        results.append({
            'snapshot_id': snapshot_id,
            'prediction': pred['predicted_label'],
            'confidence': pred['confidence'],
            'risk_level': pred['risk_level']
        })
    except Exception as e:
        print(f"Error on {snapshot_id}: {e}")

# Save results
results_df = pd.DataFrame(results)
results_df.to_csv('outputs/batch_predictions.csv', index=False)
```

---

## Output Files

After training, the following files are created in `outputs/`:

```
outputs/
├── best_model.pt              # Best model checkpoint
├── final_model.pt             # Final model checkpoint
├── scalers.pkl                # Fitted data scalers
├── training_history.json      # Training metrics history
├── training_curves.png        # Loss/accuracy plots
├── confusion_matrix.png       # Confusion matrix visualization
├── roc_curve.png             # ROC curve
└── test_metrics.json         # Test set evaluation metrics
```

---

## Troubleshooting

### Issue: CUDA Out of Memory

**Solution**:
```python
# Reduce batch size
config['batch_size'] = 16  # or 8

# Or use CPU
device = 'cpu'
```

### Issue: Poor Performance

**Possible causes**:
1. **Class imbalance** - Collect more normal data
2. **Insufficient training** - Increase epochs
3. **Overfitting** - Increase dropout, reduce model size
4. **Underfitting** - Increase model size, reduce dropout

**Solutions**:
```python
# For class imbalance
config['use_focal_loss'] = True
config['focal_gamma'] = 2.5  # Focus more on hard examples

# For overfitting
config['dropout'] = 0.5
config['weight_decay'] = 0.02

# For underfitting
config['hidden_dim'] = 256
config['num_gat_layers'] = 4
```

### Issue: Training Too Slow

**Solutions**:
```bash
# Use GPU
export CUDA_VISIBLE_DEVICES=0

# Reduce data size (for testing)
# Edit dataset.py to use subset

# Increase batch size (if memory allows)
config['batch_size'] = 64
```

### Issue: Import Errors

```bash
# Reinstall PyTorch Geometric
pip uninstall torch-geometric torch-scatter torch-sparse
pip install torch-geometric torch-scatter torch-sparse

# Or install from source
pip install git+https://github.com/pyg-team/pytorch_geometric.git
```

---

## Model Interpretation

### Understanding Predictions

```python
prediction = {
    'predicted_class': 1,              # 0=normal, 1=pre_failure
    'predicted_label': 'pre_failure',  # Human-readable
    'confidence': 0.87,                # Model confidence
    'probabilities': {
        'normal': 0.13,
        'pre_failure': 0.87
    },
    'risk_level': 'high'               # low/medium/high/critical
}
```

### Risk Levels

| Risk Level | Failure Probability | Action |
|-----------|---------------------|--------|
| **Low** | < 30% | Normal monitoring |
| **Medium** | 30-50% | Increased monitoring |
| **High** | 50-70% | Alert operators |
| **Critical** | > 70% | Immediate action required |

---

## Advanced Features

### 1. Temporal Sequences

Enable temporal attention for sequence-based predictions:

```python
config['use_temporal'] = True
config['seq_length'] = 5  # Use 5 consecutive snapshots
```

### 2. Custom Loss Functions

Implement custom loss in `gnn_model.py`:

```python
class CustomLoss(nn.Module):
    def forward(self, inputs, targets):
        # Your custom loss logic
        pass
```

### 3. Model Ensemble

Combine multiple models for better predictions:

```python
models = [
    FailurePredictor('outputs/model1.pt'),
    FailurePredictor('outputs/model2.pt'),
    FailurePredictor('outputs/model3.pt')
]

# Average predictions
predictions = [m.predict(data) for m in models]
avg_prob = np.mean([p['probabilities']['pre_failure'] for p in predictions])
```

---

## Integration with K8s

### Real-Time Monitoring

```python
from inference import FailurePredictor
from src.collectors.prometheus_collector import PrometheusCollector
from src.collectors.k8s_collector import K8sCollector
import time

# Initialize
predictor = FailurePredictor()
prom = PrometheusCollector()
k8s = K8sCollector()

# Monitoring loop
while True:
    # Collect current state
    metrics = prom.collect_snapshot()
    topology = k8s.collect_topology()
    
    # Predict
    prediction = predictor.predict_from_snapshot(metrics, topology)
    
    # Take action based on risk level
    if prediction['risk_level'] in ['high', 'critical']:
        print(f"⚠️  WARNING: {prediction['risk_level']} risk detected!")
        print(f"   Failure probability: {prediction['probabilities']['pre_failure']:.2%}")
        # Send alert, scale resources, etc.
    
    time.sleep(30)  # Check every 30 seconds
```

---

## Performance Optimization

### 1. Model Quantization

Reduce model size for deployment:

```python
import torch

# Load model
model = torch.load('outputs/best_model.pt')

# Quantize
quantized_model = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)

# Save
torch.save(quantized_model, 'outputs/quantized_model.pt')
```

### 2. ONNX Export

Export for production deployment:

```python
import torch.onnx

# Dummy input
dummy_x = torch.randn(10, 11)
dummy_edge_index = torch.randint(0, 10, (2, 15))
dummy_batch = torch.zeros(10, dtype=torch.long)

# Export
torch.onnx.export(
    model,
    (dummy_x, dummy_edge_index, dummy_batch),
    'outputs/model.onnx',
    input_names=['x', 'edge_index', 'batch'],
    output_names=['logits'],
    dynamic_axes={'x': {0: 'num_nodes'}, 'edge_index': {1: 'num_edges'}}
)
```

---

## Citation

If you use this model in your research, please cite:

```bibtex
@software{k8s_failure_gnn,
  title={GNN-based Failure Prediction for Kubernetes Clusters},
  author={Your Name},
  year={2026},
  url={https://github.com/yourusername/k8s-failure-prevention-gnn}
}
```

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review training logs in `outputs/`
3. Verify data quality and balance
4. Check PyTorch Geometric installation

---

## Next Steps

1. **Collect balanced data** (see `README_DATA_COLLECTION.md`)
2. **Train baseline model** with default config
3. **Evaluate performance** on test set
4. **Tune hyperparameters** based on results
5. **Deploy for real-time monitoring**

**Remember**: Model quality depends on data quality. Ensure balanced, high-quality training data!