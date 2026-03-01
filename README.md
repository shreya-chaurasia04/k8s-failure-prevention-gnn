# Install kind

```
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```
# Install kubectl

```
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```


## Kind with Docker
# Create cluster

`kind create cluster --config cluster-config.yaml --name gnn-cluster`

# Verify nodes
`kubectl get nodes`

# Check cluster info
`kubectl cluster-info --context kind-gnn-cluster`

# Verify control plane components
`kubectl get pods -n kube-system`


## Kind with Podman
# Set kind to use podman
`export KIND_EXPERIMENTAL_PROVIDER=podman`

# Start podman machine (if not running)
`podman machine start`

# Verify podman works
`podman ps`

# Create cluster with podman
`KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster --config cluster-config.yaml --name gnn-cluster`

# Set alias for convenience (optional)
```
echo 'export KIND_EXPERIMENTAL_PROVIDER=podman' >> ~/.zshrc
source ~/.zshrc
```

# Verify nodes
`kubectl get nodes`

# Check control plane
`kubectl get pods -n kube-system`
