from kubernetes import client, config

class K8sCollector:
    def __init__(self):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
    
    def collect_topology(self):
        pods = self.v1.list_namespaced_pod('workload')
        nodes = self.v1.list_node()
        
        return {
            'pods': [{
                'name': p.metadata.name,
                'namespace': p.metadata.namespace,
                'node': p.spec.node_name,
                'status': p.status.phase,
                'labels': p.metadata.labels
            } for p in pods.items],
            'nodes': [{
                'name': n.metadata.name,
                'labels': n.metadata.labels
            } for n in nodes.items]
        }
