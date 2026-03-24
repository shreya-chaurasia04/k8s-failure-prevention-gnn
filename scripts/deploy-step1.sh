#!/bin/bash
# Step 1: Deploy Enhanced Prometheus Monitoring

echo "Deploying kube-state-metrics..."
kubectl apply -f kube-state-metrics.yaml

echo "Deploying node-exporter..."
kubectl apply -f node-exporter.yaml

echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/kube-state-metrics -n monitoring
kubectl wait --for=condition=ready --timeout=60s pod -l app=node-exporter -n monitoring

echo "Updating Prometheus configuration..."
kubectl apply -f prometheus-config-enhanced.yaml

echo "Restarting Prometheus to apply new config..."
kubectl rollout restart deployment/prometheus-deployment -n monitoring
kubectl rollout status deployment/prometheus-deployment -n monitoring

echo "✓ Step 1 Complete. Verify targets at http://localhost:9090/targets"