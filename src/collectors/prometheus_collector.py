from prometheus_api_client import PrometheusConnect
import json
from datetime import datetime

class PrometheusCollector:
    def __init__(self, url='http://localhost:9090'):
        self.prom = PrometheusConnect(url=url, disable_ssl=True)
    
    def collect_snapshot(self):
        return {
            'timestamp': datetime.now().isoformat(),
            'pod_cpu': self.prom.custom_query('sum(rate(container_cpu_usage_seconds_total{namespace="workload"}[1m])) by (pod, node)'),
            'pod_memory': self.prom.custom_query('sum(container_memory_working_set_bytes{namespace="workload"}) by (pod, node)'),
            'node_cpu': self.prom.custom_query('sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (instance)'),
            'node_memory': self.prom.custom_query('node_memory_Active_bytes'),
            'apiserver_latency': self.prom.custom_query('apiserver_request_duration_seconds_sum'),
            'pod_restarts': self.prom.custom_query('kube_pod_container_status_restarts_total{namespace="workload"}')
        }
