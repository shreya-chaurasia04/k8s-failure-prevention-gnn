import torch
import torch.nn as nn
import glob
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns
import matplotlib.pyplot as plt
from torch_geometric.loader import DataLoader

from processor.ClusterGraphArchitect import ClusterGraphArchitect
from models.GINconv import GNNStack 

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"🚀 Training on: {device}")

# 2. Data Loading & Processing
def prepare_dataset():
    arch = ClusterGraphArchitect()
    all_graphs = []
    
    # Process Baseline (Label 0)
    for f in glob.glob("data/baseline/*.csv"):
        all_graphs.extend(arch.create_graph(f))
    
    # Process Failure (Label 1, 2, 3, 4)
    for f in glob.glob("data/failure/*.csv"):
        all_graphs.extend(arch.create_graph(f))
        
    torch.manual_seed(42)
    all_graphs = [g for g in all_graphs if g is not None]
    perm = torch.randperm(len(all_graphs))
    all_graphs = [all_graphs[i] for i in perm]
    
    split = int(len(all_graphs) * 0.8)
    return all_graphs[:split], all_graphs[split:]

train_data, test_data = prepare_dataset()
train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
test_loader = DataLoader(test_data, batch_size=32, shuffle=False)

# 3. Model setup
# Updated: input_dim=4 (original features), output_dim=5 (5 failure classes)
model = GNNStack(input_dim=4, hidden_dim=32, output_dim=5, num_layers=3).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=5e-4)
criterion = nn.CrossEntropyLoss()

def train():
    model.train()
    total_loss = 0
    for data in train_loader:
        data = data.to(device)
        optimizer.zero_grad()
        out = model(data)
        loss = criterion(out, data.y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * data.num_graphs
    return total_loss / len(train_loader.dataset)

def test(loader):
    model.eval()
    correct = 0
    for data in loader:
        data = data.to(device)
        out = model(data)
        pred = out.argmax(dim=1)
        correct += int((pred == data.y).sum())
    return correct / len(loader.dataset)

def evaluate_model(loader, title="Final Validation"):
    model.eval()
    all_preds = []
    all_labels = []

    target_names = ['Healthy', 'Etcd-Fail', 'API-Fail', 'CPU-Stress', 'Memory-Stress']
    
    with torch.no_grad():
        for data in loader:
            data = data.to(device)
            out = model(data)
            pred = out.argmax(dim=1)
            all_preds.extend(pred.cpu().numpy())
            all_labels.extend(data.y.cpu().numpy())

    # prints Precision, Recall, and F1-Score
    print(f"\n--- {title} Classification Report ---")
    print(classification_report(all_labels, all_preds, target_names=target_names))

    # Confusion Matrix Visualization
    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Purples', 
                xticklabels=target_names, 
                yticklabels=target_names)
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.title(f'Confusion Matrix - {title}')
    plt.savefig("confusion_matrix_2.png") # Saves a copy to the folder
    print("📈 Confusion Matrix saved as confusion_matrix_2.png")
    plt.show()

# 5. Run Training Loop
print(f"📊 Dataset: {len(train_data)} train, {len(test_data)} test.")
for epoch in range(1, 151):
    loss = train()
    if epoch % 10 == 0:
        train_acc = test(train_loader)
        test_acc = test(test_loader)
        print(f'Epoch: {epoch:03d}, Loss: {loss:.4f}, Train Acc: {train_acc:.4f}, Test Acc: {test_acc:.4f}')

# 6. Evaluation and Save
evaluate_model(test_loader)
torch.save(model.state_dict(), "models/gnn_failure_model.pt")
print("✅ Model brain saved as gnn_failure_model.pt")