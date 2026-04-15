#!/bin/bash

# Fix etcd metrics exposure for Prometheus
# This script updates etcd to expose metrics on 0.0.0.0 instead of 127.0.0.1

set -e

echo "=========================================================================="
echo "  FIXING ETCD METRICS EXPOSURE"
echo "=========================================================================="
echo ""

# Find the control plane container
CONTROL_PLANE=$(docker ps --filter "name=control-plane" --format "{{.Names}}" | head -n 1)

if [ -z "$CONTROL_PLANE" ]; then
    echo "❌ Error: Could not find control-plane container"
    echo "   Run: docker ps | grep control-plane"
    exit 1
fi

echo "✅ Found control plane container: $CONTROL_PLANE"
echo ""

# Check current etcd configuration
echo "🔍 Checking current etcd metrics configuration..."
docker exec -it $CONTROL_PLANE cat /etc/kubernetes/manifests/etcd.yaml | grep listen-metrics || true
echo ""

# Fix etcd metrics URL
echo "🔧 Updating etcd to expose metrics on 0.0.0.0:2381..."
docker exec -it $CONTROL_PLANE sed -i 's/--listen-metrics-urls=http:\/\/127.0.0.1:2381/--listen-metrics-urls=http:\/\/0.0.0.0:2381/g' /etc/kubernetes/manifests/etcd.yaml

echo "✅ etcd configuration updated"
echo ""

# Also fix scheduler and controller-manager while we're at it
echo "🔧 Updating scheduler metrics..."
docker exec -it $CONTROL_PLANE sed -i 's/--bind-address=127.0.0.1/--bind-address=0.0.0.0/g' /etc/kubernetes/manifests/kube-scheduler.yaml

echo "🔧 Updating controller-manager metrics..."
docker exec -it $CONTROL_PLANE sed -i 's/--bind-address=127.0.0.1/--bind-address=0.0.0.0/g' /etc/kubernetes/manifests/kube-controller-manager.yaml

echo ""
echo "⏳ Waiting 30 seconds for pods to restart..."
sleep 30

echo ""
echo "🔍 Verifying etcd pod is running..."
kubectl get pods -n kube-system | grep etcd

echo ""
echo "=========================================================================="
echo "✅ ETCD METRICS FIX COMPLETE"
echo "=========================================================================="
echo ""
echo "Next steps:"
echo "  1. Wait 1-2 minutes for Prometheus to scrape"
echo "  2. Check Prometheus targets: http://localhost:9090/targets"
echo "  3. etcd target should now show UP"
echo ""
echo "If still DOWN, check the error message in Prometheus targets page."
echo ""

# Made with Bob
