Forward the prometheus port (if not accessible) e.g.

```shell
kubectl port-forward prometheus-prometheus-kube-prometheus-prometheus-0 9090:9090
```

an set env variable pointing to Prometheus API e.g. (note that trailing slash is required )

```text
PROMETHEUS_URL=http://localhost:9090/prometheus/
```

Code from `cpt.hackathon` moved to `cpt.prometheus` package. Branch `hackathon` is kept 

[demo.md](../hackathon/demo.md) and [hackathon.pdf](../hackathon/hackathon.pdf) are in `cpt.hackathon` 