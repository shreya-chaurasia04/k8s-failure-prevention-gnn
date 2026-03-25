import torch
import torch.nn as nn
import os
import glob
from torch_geometric.loader import DataLoader
from processor.etcd_failure_graph_factory import ClusterGraphArchitect
from models.GINconv import GNNStack # Ensure your model class name matches

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"🚀 Training on: {device}")

# 2. Data Loading & Processing
def prepare_dataset():
    arch = ClusterGraphArchitect()
    all_graphs = []
    
    # Process Baseline (Label 0)
    for f in glob.glob("../data/baseline/*.csv"):
        all_graphs.extend(arch.create_graph(f))
    
    # Process Failure (Label 1)
    for f in glob.glob("../data/failure/*.csv"):
        all_graphs.extend(arch.create_graph(f))
        
    # Shuffle and Split (80% Train, 20% Test)
    torch.manual_seed(42)
    all_graphs = [g for g in all_graphs if g is not None]
    perm = torch.randperm(len(all_graphs))
    all_graphs = [all_graphs[i] for i in perm]
    
    split = int(len(all_graphs) * 0.8)
    return all_graphs[:split], all_graphs[split:]

train_data, test_data = prepare_dataset()
train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
test_loader = DataLoader(test_data, batch_size=32, shuffle=False)

# 3. Model, Optimizer, and Loss
# input_dim = 3 (api_rate, etcd_fsync, pod_cpu), output_dim = 2 (Healthy/Failure)
model = GNNStack(input_dim=3, hidden_dim=32, output_dim=2, num_layers=3).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)
criterion = nn.CrossEntropyLoss()

# 4. Training Loop
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

# 5. Run Training
print(f"📊 Training on {len(train_data)} graphs, testing on {len(test_data)}...")
for epoch in range(1, 101):
    loss = train()
    train_acc = test(train_loader)
    test_acc = test(test_loader)
    if epoch % 10 == 0:
        print(f'Epoch: {epoch:03d}, Loss: {loss:.4f}, Train Acc: {train_acc:.4f}, Test Acc: {test_acc:.4f}')

# 6. Save the Brain
torch.save(model.state_state_dict(), "gnn_failure_model.pt")
print("✅ Model saved as gnn_failure_model.pt")