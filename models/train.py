"""
Training script for K8s Failure Prediction GNN

This module provides training, validation, and evaluation functions for the GNN model.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau, CosineAnnealingLR
import numpy as np
from pathlib import Path
import json
import time
from typing import Dict, Tuple, Optional
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score, roc_curve
)

from gnn_model import K8sFailurePredictionGNN, FocalLoss, create_model
from dataset import create_dataloaders


class Trainer:
    """
    Trainer class for K8s Failure Prediction GNN.
    Handles training, validation, and evaluation.
    """
    
    def __init__(
        self,
        model: K8sFailurePredictionGNN,
        train_loader,
        val_loader,
        test_loader,
        config: Dict,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        """
        Args:
            model: GNN model
            train_loader: Training dataloader
            val_loader: Validation dataloader
            test_loader: Test dataloader
            config: Training configuration
            device: Device to train on
        """
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.config = config
        self.device = device
        
        # Loss function
        if config.get('use_focal_loss', True):
            self.criterion = FocalLoss(
                alpha=config.get('focal_alpha', 0.25),
                gamma=config.get('focal_gamma', 2.0)
            )
        else:
            # Use class weights for standard cross-entropy
            class_weights = train_loader.dataset.get_class_weights().to(device)
            self.criterion = nn.CrossEntropyLoss(weight=class_weights)
        
        # Optimizer
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=config.get('learning_rate', 0.001),
            weight_decay=config.get('weight_decay', 0.01)
        )
        
        # Learning rate scheduler
        if config.get('scheduler', 'plateau') == 'plateau':
            self.scheduler = ReduceLROnPlateau(
                self.optimizer,
                mode='min',
                factor=0.5,
                patience=5,
                verbose=True
            )
        else:
            self.scheduler = CosineAnnealingLR(
                self.optimizer,
                T_max=config.get('epochs', 100)
            )
        
        # Training history
        self.history = {
            'train_loss': [],
            'train_acc': [],
            'val_loss': [],
            'val_acc': [],
            'val_f1': [],
            'learning_rate': []
        }
        
        # Best model tracking
        self.best_val_f1 = 0.0
        self.best_epoch = 0
        
        # Output directory
        self.output_dir = Path(config.get('output_dir', 'outputs'))
        self.output_dir.mkdir(exist_ok=True)
    
    def train_epoch(self) -> Tuple[float, float]:
        """
        Train for one epoch.
        
        Returns:
            avg_loss: Average training loss
            avg_acc: Average training accuracy
        """
        self.model.train()
        total_loss = 0
        all_preds = []
        all_labels = []
        
        pbar = tqdm(self.train_loader, desc='Training')
        for batch in pbar:
            batch = batch.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            logits = self.model(batch.x, batch.edge_index, batch.batch)
            loss = self.criterion(logits, batch.y)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            if self.config.get('grad_clip', 0) > 0:
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config['grad_clip']
                )
            
            self.optimizer.step()
            
            # Track metrics
            total_loss += loss.item() * batch.num_graphs
            preds = logits.argmax(dim=1).cpu().numpy()
            labels = batch.y.cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels)
            
            # Update progress bar
            pbar.set_postfix({'loss': loss.item()})
        
        avg_loss = total_loss / len(self.train_loader.dataset)
        avg_acc = accuracy_score(all_labels, all_preds)
        
        return avg_loss, avg_acc
    
    @torch.no_grad()
    def validate(self) -> Tuple[float, float, float, Dict]:
        """
        Validate the model.
        
        Returns:
            avg_loss: Average validation loss
            avg_acc: Average validation accuracy
            avg_f1: Average F1 score
            metrics: Dictionary of detailed metrics
        """
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        all_probs = []
        
        for batch in self.val_loader:
            batch = batch.to(self.device)
            
            # Forward pass
            logits = self.model(batch.x, batch.edge_index, batch.batch)
            loss = self.criterion(logits, batch.y)
            
            # Track metrics
            total_loss += loss.item() * batch.num_graphs
            probs = torch.softmax(logits, dim=1)
            preds = logits.argmax(dim=1).cpu().numpy()
            labels = batch.y.cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(labels)
            all_probs.extend(probs[:, 1].cpu().numpy())  # Probability of positive class
        
        avg_loss = total_loss / len(self.val_loader.dataset)
        avg_acc = accuracy_score(all_labels, all_preds)
        avg_f1 = f1_score(all_labels, all_preds, average='weighted')
        
        # Detailed metrics
        metrics = {
            'accuracy': avg_acc,
            'precision': precision_score(all_labels, all_preds, average='weighted', zero_division=0),
            'recall': recall_score(all_labels, all_preds, average='weighted', zero_division=0),
            'f1': avg_f1,
            'confusion_matrix': confusion_matrix(all_labels, all_preds).tolist()
        }
        
        # ROC-AUC if binary classification
        if len(np.unique(all_labels)) == 2:
            metrics['roc_auc'] = roc_auc_score(all_labels, all_probs)
        
        return avg_loss, avg_acc, avg_f1, metrics
    
    def train(self, epochs: int, early_stopping_patience: int = 10):
        """
        Train the model for multiple epochs.
        
        Args:
            epochs: Number of epochs to train
            early_stopping_patience: Patience for early stopping
        """
        print(f"Training on {self.device}")
        print(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
        print("-" * 80)
        
        patience_counter = 0
        
        for epoch in range(epochs):
            start_time = time.time()
            
            # Train
            train_loss, train_acc = self.train_epoch()
            
            # Validate
            val_loss, val_acc, val_f1, val_metrics = self.validate()
            
            # Update learning rate
            if isinstance(self.scheduler, ReduceLROnPlateau):
                self.scheduler.step(val_loss)
            else:
                self.scheduler.step()
            
            # Track history
            self.history['train_loss'].append(train_loss)
            self.history['train_acc'].append(train_acc)
            self.history['val_loss'].append(val_loss)
            self.history['val_acc'].append(val_acc)
            self.history['val_f1'].append(val_f1)
            self.history['learning_rate'].append(self.optimizer.param_groups[0]['lr'])
            
            # Print progress
            epoch_time = time.time() - start_time
            print(f"Epoch {epoch+1}/{epochs} ({epoch_time:.2f}s)")
            print(f"  Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.4f}")
            print(f"  Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | Val F1: {val_f1:.4f}")
            print(f"  LR: {self.optimizer.param_groups[0]['lr']:.6f}")
            
            # Save best model
            if val_f1 > self.best_val_f1:
                self.best_val_f1 = val_f1
                self.best_epoch = epoch
                self.save_checkpoint('best_model.pt')
                print(f"  ✓ New best model saved (F1: {val_f1:.4f})")
                patience_counter = 0
            else:
                patience_counter += 1
            
            # Early stopping
            if patience_counter >= early_stopping_patience:
                print(f"\nEarly stopping triggered after {epoch+1} epochs")
                break
            
            print("-" * 80)
        
        print(f"\nTraining complete!")
        print(f"Best epoch: {self.best_epoch+1} with F1: {self.best_val_f1:.4f}")
        
        # Save final model and history
        self.save_checkpoint('final_model.pt')
        self.save_history()
        self.plot_training_curves()
    
    @torch.no_grad()
    def evaluate(self, loader=None) -> Dict:
        """
        Evaluate the model on test set.
        
        Args:
            loader: Dataloader to evaluate on (default: test_loader)
        
        Returns:
            metrics: Dictionary of evaluation metrics
        """
        if loader is None:
            loader = self.test_loader
        
        self.model.eval()
        all_preds = []
        all_labels = []
        all_probs = []
        
        print("Evaluating model...")
        for batch in tqdm(loader):
            batch = batch.to(self.device)
            
            # Forward pass
            logits = self.model(batch.x, batch.edge_index, batch.batch)
            probs = torch.softmax(logits, dim=1)
            preds = logits.argmax(dim=1).cpu().numpy()
            labels = batch.y.cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(labels)
            all_probs.extend(probs[:, 1].cpu().numpy())
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(all_labels, all_preds),
            'precision': precision_score(all_labels, all_preds, average='weighted', zero_division=0),
            'recall': recall_score(all_labels, all_preds, average='weighted', zero_division=0),
            'f1': f1_score(all_labels, all_preds, average='weighted'),
            'confusion_matrix': confusion_matrix(all_labels, all_preds).tolist(),
            'classification_report': classification_report(all_labels, all_preds, target_names=['Normal', 'Pre-Failure'])
        }
        
        # ROC-AUC if binary classification
        if len(np.unique(all_labels)) == 2:
            metrics['roc_auc'] = roc_auc_score(all_labels, all_probs)
            
            # Plot ROC curve
            self.plot_roc_curve(all_labels, all_probs)
        
        # Plot confusion matrix
        self.plot_confusion_matrix(metrics['confusion_matrix'])
        
        # Save metrics
        with open(self.output_dir / 'test_metrics.json', 'w') as f:
            # Convert numpy arrays to lists for JSON serialization
            json_metrics = {k: v if not isinstance(v, np.ndarray) else v.tolist() 
                           for k, v in metrics.items() if k != 'classification_report'}
            json_metrics['classification_report'] = metrics['classification_report']
            json.dump(json_metrics, f, indent=2)
        
        print("\nTest Results:")
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  F1 Score: {metrics['f1']:.4f}")
        if 'roc_auc' in metrics:
            print(f"  ROC-AUC: {metrics['roc_auc']:.4f}")
        print("\nClassification Report:")
        print(metrics['classification_report'])
        
        return metrics
    
    def save_checkpoint(self, filename: str):
        """Save model checkpoint."""
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'config': self.config,
            'history': self.history,
            'best_val_f1': self.best_val_f1,
            'best_epoch': self.best_epoch
        }
        torch.save(checkpoint, self.output_dir / filename)
    
    def load_checkpoint(self, filename: str):
        """Load model checkpoint."""
        checkpoint = torch.load(self.output_dir / filename, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        self.history = checkpoint['history']
        self.best_val_f1 = checkpoint['best_val_f1']
        self.best_epoch = checkpoint['best_epoch']
    
    def save_history(self):
        """Save training history."""
        with open(self.output_dir / 'training_history.json', 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def plot_training_curves(self):
        """Plot training curves."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Loss
        axes[0, 0].plot(self.history['train_loss'], label='Train')
        axes[0, 0].plot(self.history['val_loss'], label='Validation')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].set_title('Training and Validation Loss')
        axes[0, 0].legend()
        axes[0, 0].grid(True)
        
        # Accuracy
        axes[0, 1].plot(self.history['train_acc'], label='Train')
        axes[0, 1].plot(self.history['val_acc'], label='Validation')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('Accuracy')
        axes[0, 1].set_title('Training and Validation Accuracy')
        axes[0, 1].legend()
        axes[0, 1].grid(True)
        
        # F1 Score
        axes[1, 0].plot(self.history['val_f1'], label='Validation F1')
        axes[1, 0].axhline(y=self.best_val_f1, color='r', linestyle='--', label=f'Best F1: {self.best_val_f1:.4f}')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('F1 Score')
        axes[1, 0].set_title('Validation F1 Score')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
        
        # Learning Rate
        axes[1, 1].plot(self.history['learning_rate'])
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('Learning Rate')
        axes[1, 1].set_title('Learning Rate Schedule')
        axes[1, 1].set_yscale('log')
        axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'training_curves.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_confusion_matrix(self, cm):
        """Plot confusion matrix."""
        plt.figure(figsize=(8, 6))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Confusion Matrix')
        plt.colorbar()
        
        classes = ['Normal', 'Pre-Failure']
        tick_marks = np.arange(len(classes))
        plt.xticks(tick_marks, classes)
        plt.yticks(tick_marks, classes)
        
        # Add text annotations
        thresh = np.array(cm).max() / 2.
        for i in range(len(classes)):
            for j in range(len(classes)):
                plt.text(j, i, format(cm[i][j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i][j] > thresh else "black")
        
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'confusion_matrix.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_roc_curve(self, labels, probs):
        """Plot ROC curve."""
        fpr, tpr, _ = roc_curve(labels, probs)
        roc_auc = roc_auc_score(labels, probs)
        
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.4f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'roc_curve.png', dpi=300, bbox_inches='tight')
        plt.close()


def main():
    """Main training function."""
    # Configuration
    config = {
        # Data
        'data_dir': 'data/processed',
        'batch_size': 32,
        'train_ratio': 0.7,
        'val_ratio': 0.15,
        'test_ratio': 0.15,
        
        # Model
        'node_feature_dim': 11,
        'hidden_dim': 128,
        'num_gat_layers': 3,
        'num_heads': 4,
        'num_classes': 2,
        'dropout': 0.3,
        'use_temporal': False,
        
        # Training
        'epochs': 100,
        'learning_rate': 0.001,
        'weight_decay': 0.01,
        'grad_clip': 1.0,
        'use_focal_loss': True,
        'focal_alpha': 0.25,
        'focal_gamma': 2.0,
        'scheduler': 'plateau',
        'early_stopping_patience': 15,
        
        # Output
        'output_dir': 'outputs',
        'random_seed': 42
    }
    
    # Set random seeds
    torch.manual_seed(config['random_seed'])
    np.random.seed(config['random_seed'])
    
    # Create dataloaders
    print("Loading data...")
    train_loader, val_loader, test_loader, dataset = create_dataloaders(
        data_dir=config['data_dir'],
        train_ratio=config['train_ratio'],
        val_ratio=config['val_ratio'],
        test_ratio=config['test_ratio'],
        batch_size=config['batch_size'],
        random_seed=config['random_seed']
    )
    
    # Save scalers
    dataset.save_scalers('outputs/scalers.pkl')
    
    # Create model
    print("\nCreating model...")
    model = create_model(config)
    
    # Create trainer
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        config=config
    )
    
    # Train
    print("\nStarting training...")
    trainer.train(
        epochs=config['epochs'],
        early_stopping_patience=config['early_stopping_patience']
    )
    
    # Load best model and evaluate
    print("\nLoading best model for evaluation...")
    trainer.load_checkpoint('best_model.pt')
    trainer.evaluate()
    
    print("\nTraining complete! Results saved to outputs/")


if __name__ == '__main__':
    main()

# Made with Bob
