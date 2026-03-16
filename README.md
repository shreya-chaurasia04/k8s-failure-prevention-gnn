# Prerequisites

## Install kind
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

## Install kubectl
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```

---

# Kind with Docker

## Create Cluster
```bash
kind create cluster --config cluster-config.yaml --name gnn-cluster
```

## Verify Nodes
```bash
kubectl get nodes
```

## Check Cluster Info
```bash
kubectl cluster-info --context kind-gnn-cluster
```

## Verify Control Plane Components
```bash
kubectl get pods -n kube-system
```

---

# Setup Prometheus and Metrics Access

## Create Namespace
```bash
kubectl create namespace monitoring
```

---

# Setup ClusterRole, ServiceAccount and Bindings for Prometheus

Create RBAC configuration:

```bash
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
```

Apply the configuration:

```bash
kubectl apply -f prometheus-rbac.yaml
```

Expected output:

```
serviceaccount/prometheus-sa created
clusterrole.rbac.authorization.k8s.io/prometheus-role created
clusterrolebinding.rbac.authorization.k8s.io/prometheus-role-binding created
```

---

# Create Prometheus ConfigMap

```bash
cat <<EOF > prometheus-config.yaml
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
          - source_labels:
              [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
            action: keep
            regex: default;kubernetes;https

      - job_name: 'kubernetes-scheduler'
        static_configs:
          - targets: ['172.18.0.2:10259']
        scheme: https
        tls_config:
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token

      - job_name: 'kubernetes-controller-manager'
        static_configs:
          - targets: ['172.18.0.2:10257']
        scheme: https
        tls_config:
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token

      - job_name: 'etcd'
        static_configs:
          - targets: ['172.18.0.2:2381']
        scheme: http
EOF
```

Apply the ConfigMap:

```bash
kubectl apply -f prometheus-config.yaml
```

Expected output:

```
configmap/prometheus-server-conf created
```

---

# Setup Prometheus Deployment

```bash
cat <<EOF > prometheus-deployment.yaml
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
```

Apply deployment:

```bash
kubectl apply -f prometheus-deployment.yaml
```

Expected output:

```
deployment.apps/prometheus-deployment created
```

---

# Access Prometheus

Port-forward Prometheus service:

```bash
kubectl port-forward deploy/prometheus-deployment 9090:9090 -n monitoring
```

Expected output:

```
Forwarding from 127.0.0.1:9090 -> 9090
Handling connection for 9090
```

Open:

```
http://localhost:9090
```

---

# Enable Metrics for Scheduler, Controller Manager and etcd

Control plane components in **kind** bind metrics to `127.0.0.1` by default.  
We must expose them on all interfaces.

```bash
docker exec -it gnn-research-control-plane bash
```

Run inside the container:

```bash
sed -i 's/--bind-address=127.0.0.1/--bind-address=0.0.0.0/g' /etc/kubernetes/manifests/kube-scheduler.yaml

sed -i 's/--bind-address=127.0.0.1/--bind-address=0.0.0.0/g' /etc/kubernetes/manifests/kube-controller-manager.yaml

sed -i 's/--listen-metrics-urls=http:\/\/127.0.0.1:2381/--listen-metrics-urls=http:\/\/0.0.0.0:2381/g' /etc/kubernetes/manifests/etcd.yaml
```

Kubernetes will automatically restart these static pods.

---

# Metrics Verification

Currently configured and scraping:

- kube-apiserver
- kube-scheduler
- kube-controller-manager
- etcd

Example Prometheus target view:

<img width="1918" height="681" alt="image" src="https://github.com/user-attachments/assets/3883c6f2-745d-42bd-9b15-05db49431e91" />

## accessing metrics from kube-api, controller, scheduler
```bash
# Pull the API Server metrics:

 kubectl --kubeconfig /etc/kubernetes/admin.conf get --raw /metrics > /tmp/apiserver_full_list.txt
grep "# HELP" /tmp/apiserver_full_list.txt | head -n 20

# Using the APIServer-Kubelet client certs to identify as a high-privilege system component scheduler
curl -k \ --cert /etc/kubernetes/pki/apiserver-kubelet-client.crt \ --key /etc/kubernetes/pki/apiserver-kubelet-client.key \ https://127.0.0.1:10259/metrics > /tmp/scheduler_full_list.txt 

# same for the Controller  

curl -k \ --cert /etc/kubernetes/pki/apiserver-kubelet-client.crt \ --key /etc/kubernetes/pki/apiserver-kubelet-client.key \ https://127.0.0.1:10257/metrics > /tmp/controller_full_list.txt
```

## output
```bash
root@gnn-research-control-plane:/# cd tmp
root@gnn-research-control-plane:/tmp# ls
apiserver_full_list.txt  controller_full_list.txt  scheduler_full_list.txt
```
view the above for scraped metrics

## Configure Data-Plane with workload.yaml - deployment and svc for frontend, backend and redis cache
```bash
root@LAPTOP-R4SU0DN5:~/K8-Project# k get svc -n workload
NAME           TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
backend-svc    ClusterIP   10.96.125.244   <none>        80/TCP     27s
frontend-svc   ClusterIP   10.96.40.30     <none>        80/TCP     27s
redis-svc      ClusterIP   10.96.215.200   <none>        6379/TCP   27s
root@LAPTOP-R4SU0DN5:~/K8-Project# k get deployments -n workload
NAME          READY   UP-TO-DATE   AVAILABLE   AGE
backend-api   2/2     2            2           38s
frontend      2/2     2            2           38s
redis-cache   1/1     1            1           38s
```
cAdvisor - container monitoring on kubelet to scrape CPU/RAM for the pods running on each of the nodes
<img width="1918" height="577" alt="image" src="https://github.com/user-attachments/assets/a67c20de-2175-49f8-ad80-a02c3b5e6473" />

