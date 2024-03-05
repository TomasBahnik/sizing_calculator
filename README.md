## Resource Analysis and Sizing

* Collects and analyses [Prometheus](https://prometheus.io/) metrics
* Estimates sizing of container resources for k8s deployment under given workload
* Contains example of LLM API prompt engineering based on [LangChain](https://www.langchain.com/) for
  generating Prometheus expressions from Grafana dashboards


### Install and test

```shell
conda env remove --name sizing_calculator
conda create --name sizing_calculator -c conda-forge python=3.11
conda activate sizing_calculator
poetry install
pytest
```
