#!/bin/bash

echo "=== Chaos Scenario Simulator ==="
echo "1. CPU Stress (5 min)"
echo "2. Memory Stress (5 min)"
echo "3. Pod Kill (random pod restart)"
echo "4. Network Delay (coming soon)"
read -p "Select scenario (1-3): " scenario

case $scenario in
  1)
    echo "Injecting CPU stress..."
    kubectl apply -f ../k8s-manifests/chaos/cpu-stress.yaml
    echo "Monitor: kubectl top pods -n workload"
    echo "Cleanup in 5 min or run: kubectl delete -f ../k8s-manifests/chaos/cpu-stress.yaml"
    ;;
  2)
    echo "Injecting memory stress..."
    kubectl apply -f ../k8s-manifests/chaos/memory-stress.yaml
    echo "Watch for OOMKilled: kubectl get pods -n workload -w"
    ;;
  3)
    echo "Killing random pod..."
    POD=$(kubectl get pods -n workload -l app=frontend -o jsonpath='{.items[0].metadata.name}')
    kubectl delete pod $POD -n workload
    echo "Deleted: $POD"
    ;;
  *)
    echo "Invalid option"
    ;;
esac
