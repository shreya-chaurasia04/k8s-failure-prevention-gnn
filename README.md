# Prerequisites
## Install kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

## Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```


# Kind with Docker
## Create cluster
kind create cluster --config cluster-config.yaml --name gnn-cluster

## Verify nodes
kubectl get nodes

## Check cluster info
kubectl cluster-info --context kind-gnn-cluster

## Verify control plane components
kubectl get pods -n kube-system


# Kind with Podman
## Set kind to use podman
export KIND_EXPERIMENTAL_PROVIDER=podman

## Start podman machine (if not running)
podman machine start

## Verify podman works
podman ps

## Create cluster with podman
KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster --config cluster-config.yaml --name gnn-cluster

## Set alias for convenience (optional)
echo 'export KIND_EXPERIMENTAL_PROVIDER=podman' >> ~/.zshrc
source ~/.zshrc
```

## Verify nodes
kubectl get nodes

## Check control plane
kubectl get pods -n kube-system

# Setup Metrics Access

### 1. Create ServiceAccount with Cluster Permissions
```bash
# Create ServiceAccount
kubectl create serviceaccount metrics-reader -n kube-system

# Grant cluster-admin permissions
kubectl create clusterrolebinding metrics-reader \
  --clusterrole=cluster-admin \
  --serviceaccount=kube-system:metrics-reader
```

### 2. Generate Authentication Token
```bash
# Generate 24-hour token
TOKEN=$(kubectl create token metrics-reader -n kube-system --duration=24h)

# Verify token was created
echo $TOKEN
```

### 3. Verify Metrics Access
```bash
# API Server metrics
curl -k -H "Authorization: Bearer $TOKEN" \
  https://127.0.0.1:6443/metrics | head -20

# Scheduler metrics
podman exec $CONTROL_PLANE curl -k \
  -H "Authorization: Bearer $TOKEN" \
  https://127.0.0.1:10259/metrics | head -20

# Controller Manager metrics
podman exec $CONTROL_PLANE curl -k \
  -H "Authorization: Bearer $TOKEN" \
  https://127.0.0.1:10257/metrics | head -20
```

**Expected Output**: Prometheus-format metrics with names like `apiserver_request_duration_seconds`, `scheduler_pending_pods`, etc.

**Note**: Token expires after 24 hours. Regenerate using the command in step 2.
