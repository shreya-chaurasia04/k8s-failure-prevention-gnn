import os
import glob
import pickle
from graph_constructor import GraphConstructor

# Get all snapshots
snapshots = sorted(glob.glob('../../data/raw/snapshot_*.json'))
print(f"Found {len(snapshots)} snapshots")

# Build graphs
graphs = []
gc = GraphConstructor()

for i, snapshot in enumerate(snapshots):
    try:
        G = gc.build_from_snapshot(snapshot)
        graphs.append({
            'timestamp': snapshot.split('_')[-1].replace('.json', ''),
            'graph': G
        })
        print(f"✓ Built graph {i+1}/{len(snapshots)}")
    except Exception as e:
        print(f"✗ Failed {snapshot}: {e}")

# Save graphs
os.makedirs('../../data/processed', exist_ok=True)
with open('../../data/processed/graphs.pkl', 'wb') as f:
    pickle.dump(graphs, f)

print(f"\nSaved {len(graphs)} graphs to data/processed/graphs.pkl")
print(f"Total nodes: {graphs[0]['graph'].number_of_nodes()}")
print(f"Total edges: {graphs[0]['graph'].number_of_edges()}")
