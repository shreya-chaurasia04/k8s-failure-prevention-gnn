import torch
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from ClusterGraphArchitect import ClusterGraphArchitect
import glob

def visualize_stress_scenario(data, scenario_name, output_file):
    """Generate visualization for a specific stress scenario."""
    arch = ClusterGraphArchitect()
    G = nx.DiGraph()
    G.add_nodes_from(arch.node_categories)
    
    # Visualization Tiers
    layers = {
        'control-plane': 0, 'worker': 0, 'worker2': 0, 'worker3': 0,
        'etcd': 1, 'apiserver': 1,
        'frontend': 2, 'backend': 2, 'redis': 2
    }
    
    # Reconstruct edges for NetworkX from the edge_index tensor
    edge_list = data.edge_index.t().tolist()
    for src, dst in edge_list:
        G.add_edge(arch.id_to_name[src], arch.id_to_name[dst])

    pos = {}
    layer_counts = {0: 0, 1: 0, 2: 0}
    for node, layer in layers.items():
        pos[node] = (layer * 4, -layer_counts[layer] * 2)
        layer_counts[layer] += 1

    # Enhanced Dynamic Color Logic based on 7 features
    colors = []
    for i in range(len(arch.node_categories)):
        feat = data.x[i]
        # Feature indices: [api_rate, etcd_fsync, pod_cpu, api_latency, node_cpu, node_memory, node_load]
        
        if feat[1] > 0.05:  # Etcd fsync high
            colors.append('#ff4d4d')  # Red - Etcd Stress
        elif feat[4] > 70:  # Node CPU > 70%
            colors.append('#ff6b35')  # Orange-Red - CPU Stress
        elif feat[5] > 70:  # Node Memory > 70%
            colors.append('#f7931e')  # Orange - Memory Stress
        elif feat[3] > 0.1:  # API Latency high
            colors.append('#9b59b6')  # Purple - API Saturation
        elif feat[2] > 0.5:  # Pod CPU high
            colors.append('#e67e22')  # Dark Orange - Workload CPU
        else:
            colors.append('#4db8ff')  # Blue - Healthy

    plt.figure(figsize=(14, 8), facecolor='#f5f6fa')
    
    status_map = {
        0: "HEALTHY BASELINE", 
        1: "ETCD DISK STRESS", 
        2: "API SATURATION",
        3: "CPU STRESS (Control Plane)",
        4: "MEMORY STRESS (Control Plane)"
    }
    current_status = status_map.get(data.y.item(), "UNKNOWN")
    
    nx.draw(G, pos, with_labels=True, node_color=colors, node_size=5000, 
            font_size=9, font_weight='bold', edge_color='#b2bec3', 
            width=1.2, arrowsize=15, connectionstyle="arc3,rad=0.05")
    
    # Add feature values as text
    feature_text = f"Features: API Rate={feat[0]:.2f}, Etcd Fsync={feat[1]:.4f}, Pod CPU={feat[2]:.2f}, API Latency={feat[3]:.4f}\n"
    feature_text += f"Node CPU={feat[4]:.1f}%, Node Memory={feat[5]:.1f}%, Node Load={feat[6]:.2f}"
    
    plt.title(f"Dynamic GNN Topology - {scenario_name}\nDetected State: {current_status}", 
              fontsize=16, fontweight='bold')
    plt.figtext(0.5, 0.02, feature_text, ha='center', fontsize=8, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Saved visualization: {output_file}")
    plt.close()

def main():
    """Generate visualizations for all stress scenarios."""
    arch = ClusterGraphArchitect()
    
    scenarios = [
        ("baseline", "structure/data/baseline/baseline_batch_1.csv", "Healthy Baseline"),
        ("etcd", "structure/data/failure/etcd_failure_batch_5.csv", "Etcd Disk Stress"),
        ("api", "structure/data/failure/api_failure_batch_5.csv", "API Saturation"),
    ]
    
    # Check if CPU and Memory failure data exists
    cpu_files = glob.glob("structure/data/failure/cpu_failure_batch_*.csv")
    memory_files = glob.glob("structure/data/failure/memory_failure_batch_*.csv")
    
    if cpu_files:
        scenarios.append(("cpu", cpu_files[4] if len(cpu_files) > 4 else cpu_files[0], "CPU Stress"))
    if memory_files:
        scenarios.append(("memory", memory_files[4] if len(memory_files) > 4 else memory_files[0], "Memory Stress"))
    
    print("🎨 Generating stress scenario visualizations...\n")
    
    for scenario_type, csv_path, scenario_name in scenarios:
        try:
            print(f"Processing {scenario_name}...")
            graphs = arch.create_graph(csv_path)
            
            if graphs and len(graphs) > 0:
                # Use the middle snapshot for visualization
                mid_idx = len(graphs) // 2
                data = graphs[mid_idx]
                
                output_file = f"structure/processor/{scenario_type}_stress.png"
                visualize_stress_scenario(data, scenario_name, output_file)
            else:
                print(f"⚠️  No graphs generated for {scenario_name}")
        except FileNotFoundError:
            print(f"⚠️  File not found: {csv_path}")
        except Exception as e:
            print(f"❌ Error processing {scenario_name}: {e}")
    
    # Generate combined visualization
    print("\n🎨 Generating combined stress visualization...")
    generate_combined_visualization(arch, scenarios)
    
    print("\n✨ All visualizations generated successfully!")

def generate_combined_visualization(arch, scenarios):
    """Generate a combined figure showing all stress scenarios."""
    fig, axes = plt.subplots(2, 3, figsize=(20, 12), facecolor='#f5f6fa')
    axes = axes.flatten()
    
    for idx, (scenario_type, csv_path, scenario_name) in enumerate(scenarios[:6]):
        try:
            graphs = arch.create_graph(csv_path)
            if not graphs:
                continue
                
            mid_idx = len(graphs) // 2
            data = graphs[mid_idx]
            
            G = nx.DiGraph()
            G.add_nodes_from(arch.node_categories)
            
            layers = {
                'control-plane': 0, 'worker': 0, 'worker2': 0, 'worker3': 0,
                'etcd': 1, 'apiserver': 1,
                'frontend': 2, 'backend': 2, 'redis': 2
            }
            
            edge_list = data.edge_index.t().tolist()
            for src, dst in edge_list:
                G.add_edge(arch.id_to_name[src], arch.id_to_name[dst])

            pos = {}
            layer_counts = {0: 0, 1: 0, 2: 0}
            for node, layer in layers.items():
                pos[node] = (layer * 4, -layer_counts[layer] * 2)
                layer_counts[layer] += 1

            colors = []
            for i in range(len(arch.node_categories)):
                feat = data.x[i]
                if feat[1] > 0.05:
                    colors.append('#ff4d4d')
                elif feat[4] > 70:
                    colors.append('#ff6b35')
                elif feat[5] > 70:
                    colors.append('#f7931e')
                elif feat[3] > 0.1:
                    colors.append('#9b59b6')
                elif feat[2] > 0.5:
                    colors.append('#e67e22')
                else:
                    colors.append('#4db8ff')
            
            ax = axes[idx]
            nx.draw(G, pos, ax=ax, with_labels=True, node_color=colors, 
                   node_size=3000, font_size=7, font_weight='bold', 
                   edge_color='#b2bec3', width=1.0, arrowsize=10)
            
            status_map = {0: "HEALTHY", 1: "ETCD STRESS", 2: "API STRESS", 
                         3: "CPU STRESS", 4: "MEMORY STRESS"}
            ax.set_title(f"{scenario_name}\n{status_map.get(data.y.item(), 'UNKNOWN')}", 
                        fontsize=12, fontweight='bold')
            
        except Exception as e:
            axes[idx].text(0.5, 0.5, f"Error: {scenario_name}", 
                          ha='center', va='center', transform=axes[idx].transAxes)
    
    # Hide unused subplots
    for idx in range(len(scenarios), 6):
        axes[idx].axis('off')
    
    plt.suptitle("Kubernetes Control Plane Stress Scenarios - GNN Topology View", 
                 fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig("structure/processor/all_stress_scenarios.png", dpi=150, bbox_inches='tight')
    print("✅ Saved combined visualization: structure/processor/all_stress_scenarios.png")
    plt.close()

if __name__ == "__main__":
    main()

# Made with Bob
