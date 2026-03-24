import os
import glob
from graph_constructor import GraphConstructor

# Get latest snapshot
snapshots = sorted(glob.glob('../../data/raw/snapshot_*.json'))
if snapshots:
    latest = snapshots[-1]
    print(f"Building graph from: {latest}")
    
    gc = GraphConstructor()
    G = gc.build_from_snapshot(latest)
    
    print(f"\nGraph Stats:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")
    
    print(f"\nNode Types:")
    pod_nodes = [n for n in G.nodes() if G.nodes[n]['type'] == 'pod']
    node_nodes = [n for n in G.nodes() if G.nodes[n]['type'] == 'node']
    print(f"  Pods: {len(pod_nodes)}")
    print(f"  Nodes: {len(node_nodes)}")
    
    print(f"\nSample Pod Features:")
    if pod_nodes:
        sample = pod_nodes[0]
        print(f"  {sample}: {G.nodes[sample]}")
else:
    print("No snapshots found yet. Wait for collection...")
