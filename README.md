# Prerequisites
## Install kind
```
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

## Install kubectl
```
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```

# Kind with Docker
## Create cluster

`kind create cluster --config cluster-config.yaml --name gnn-cluster`

## Verify nodes
`kubectl get nodes`

## Check cluster info
`kubectl cluster-info --context kind-gnn-cluster`

## Verify control plane components
`kubectl get pods -n kube-system`

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




## setup cluster-role, sa and bindings:
cat <<EOF > prometheus-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus-sa
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-role
rules:
- apiGroups: [""]
  resources: ["nodes", "nodes/proxy", "services", "endpoints", "pods"]
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["/metrics"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus-role
subjects:
- kind: ServiceAccount
  name: prometheus-sa
  namespace: monitoring
EOF

kubectl apply -f prometheus-rbac.yaml
serviceaccount/prometheus-sa created
clusterrole.rbac.authorization.k8s.io/prometheus-role created
clusterrolebinding.rbac.authorization.k8s.io/prometheus-role-binding created

# Create CONFIGMAP

root@LAPTOP-R4SU0DN5:~/K8-Project# cat <<EOF > prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-server-conf
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 5s
      evaluation_interval: 5s
    scrape_configs:
      - job_name: 'kubernetes-apiserver'
        kubernetes_sd_configs:
        - role: endpoints
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        relabel_configs:
        - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
          action: keep
          regex: default;kubernetes;https
EOF

kubectl apply -f prometheus-config.yaml
configmap/prometheus-server-conf created

# setup prometheus deployment
root@LAPTOP-R4SU0DN5:~/K8-Project# cat <<EOF > prometheus-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus-deployment
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus-server
  template:
    metadata:
      labels:
        app: prometheus-server
    spec:
      serviceAccountName: prometheus-sa
      containers:
        - name: prometheus
          image: prom/prometheus:v2.45.0
          args:
            - "--config.file=/etc/prometheus/prometheus.yml"
            - "--storage.tsdb.path=/prometheus/"
          ports:
            - containerPort: 9090
          volumeMounts:
            - name: prometheus-config-volume
              mountPath: /etc/prometheus/
            - name: prometheus-storage-volume
              mountPath: /prometheus/
      volumes:
        - name: prometheus-config-volume
          configMap:
            name: prometheus-server-conf
        - name: prometheus-storage-volume
          emptyDir: {}
EOF
kubectl apply -f prometheus-deployment.yaml
deployment.apps/prometheus-deployment created

## port forward with command:
root@LAPTOP-R4SU0DN5:~/K8-Project# kubectl port-forward deploy/prometheus-deployment 9090:9090 -n monitoring
Forwarding from 127.0.0.1:9090 -> 9090
Forwarding from [::1]:9090 -> 9090
Handling connection for 9090
Handling connection for 9090
Handling connection for 9090
root@LAPTOP-R4SU0DN5:~/K8-Project# kubectl port-forward deploy/prometheus-deployment 9090:9090 -n monitoring
Forwarding from 127.0.0.1:9090 -> 9090
Forwarding from [::1]:9090 -> 9090
Handling connection for 9090
Handling connection for 9090
Handling connection for 9090

## configured for kube-apiserver for now
<img width="1918" height="681" alt="image" src="https://github.com/user-attachments/assets/3883c6f2-745d-42bd-9b15-05db49431e91" />
