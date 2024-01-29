from __future__ import annotations

from typing import List

from metrics import NON_EMPTY_CONTAINER


def basic(metric: str, namespace: str, containers: str, grp_keys: str):
    labels = f'namespace=~"{namespace}",container=~"{containers}"'
    # sum(container_memory_working_set_bytes{namespace="product",container=~".+"}) by (container, pod)
    q = f"sum({metric}{{{labels}}}) by {grp_keys}"
    return q


def sum_irate(
    metric: str,
    rate_interval: str,
    namespace: str,
    containers: str,
    grp_keys: List[str],
):
    labels = f'namespace=~"{namespace}",container=~"{containers}"'
    # sum(irate(container_cpu_usage_seconds_total{container!="", namespace=~"one.+"}[1m])) by (namespace, pod)
    q = f'sum(irate({metric}{{{labels}}}[{rate_interval}])) by ({",".join(grp_keys)})'
    return q


def query_jvm(metric: str, namespace: str, containers: str, grp_keys: str, area: str):
    labels = f'{{namespace=~"{namespace}",container=~"{containers}",area="{area}"}}'
    q = f"sum({metric}{labels}) by {grp_keys}"
    return q


def cpu_throttled(namespace: str, grp_keys: str):
    """
    from https://github.com/kubernetes-monitoring/kubernetes-mixin.git
    kubernetes-mixin/dashboards/resources/pod.libsonnet
    from grafana
    sum(increase(container_cpu_cfs_throttled_periods_total
    labels {namespace="$namespace", pod="$pod", container!="POD", container!="", clusterName="$cluster"}
    range [5m])) by (container)
    / sum(increase(container_cpu_cfs_periods_total{namespace="$namespace", pod="$pod", container!="POD", container!="",
    clusterName="$cluster"}[5m])) by (container)
    if > 25% then restart
    """
    cadvisor_selector = f'job="kubelet", metrics_path="/metrics/cadvisor"'
    labels = f'{{{cadvisor_selector}, {NON_EMPTY_CONTAINER}, namespace="{namespace}"}}'
    time_range = "[5m]"
    q1 = f"sum(increase(container_cpu_cfs_throttled_periods_total{labels}{time_range})) by {grp_keys}"
    q2 = f"sum(increase(container_cpu_cfs_periods_total{labels}{time_range})) by {grp_keys}"
    q = f"{q1} / {q2}"
    return q


def pod_restarts(namespace: str, grp_keys: str):
    """
    max(kube_pod_container_status_restarts_total{container=~".+", namespace="default"}) by (pod)
    only single value by pod so the sum = max = min of this metric except for count (=1)
    :param namespace:
    :param grp_keys
    :return:
    """
    labels = f'{{{NON_EMPTY_CONTAINER}, namespace=~"{namespace}"}}'
    q = f"max(kube_pod_container_status_restarts_total{labels}) by {grp_keys}"
    return q


def jvm_gc(namespace: str, grp_keys: str, function: str = "delta", period: str = "[1m]"):
    """
    Collections : rate(jvm_gc_pause_seconds_count{namespace="product", pod="mmm-be-7b897fbc6b-pccvj"}[1m])
    Pause duration : rate(jvm_gc_pause_seconds_sum{namespace="product"}[1m])/rate(jvm_gc_pause_seconds_count{namespace="product"}[1m])
                    jvm_gc_pause_seconds_max{namespace="product"}
    :param namespace:
    :param grp_keys:
    :param function, range vector function : delta, rate
    :param period
    :return: avg GC pause duration is seconds
    """
    labels = f'{{{NON_EMPTY_CONTAINER}, namespace=~"{namespace}"}}'
    # jvm_gc_pause_seconds_count :The total number of observations for: Time spent in GC pause
    # {action="end of minor GC", cause="G1 Humongous Allocation", pod="mmm-be-7b897fbc6b-pccvj"}
    gc_count = f"sum({function}(jvm_gc_pause_seconds_count{labels}{period})) by {grp_keys}"
    # jvm_gc_pause_seconds_sum : The total sum of observations for: Time spent in GC pause
    gc_sum_sec = f"sum({function}(jvm_gc_pause_seconds_sum{labels}{period})) by {grp_keys}"
    q = f"{gc_sum_sec}/{gc_count}"
    return q
