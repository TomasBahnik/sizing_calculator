## Resource Analysis and Sizing

* Collects and analyses [Prometheus](https://prometheus.io/) metrics
* Estimates sizing of container resources for k8s deployment under given workload
* Contains example of LLM API prompt engineering based on [LangChain](https://www.langchain.com/) for
  generating Prometheus expressions from Grafana dashboards

### Install and test

* install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

```shell
conda env remove --name sizing_calculator
conda create --name sizing_calculator -c conda-forge python=3.11
conda activate sizing_calculator
# https://python-poetry.org/docs/#installing-with-the-official-installer
# Poetry should always be installed in a dedicated virtual environment to isolate it 
# from the rest of your system. 
# It should in no case be installed in the environment of the project that is to be managed by Poetry
# If you do not want to install the current project use --no-root.
poetry install --no-root
pytest -svv
```

### CLI Commands

On Windows use `python <script>.py` instead of `./<script>.py`.

* `./main.py --help` or `python main.py --help`) - - show main resource analysis commands
  (requires access to Prometheus and Snowflake).
* `./llm.py --help` - LLM few shot prompts from Grafana dashboards to generate Prometheus expressions  
  (requires `LLM_API_URL` and `LLM_API_KEY` env vars), Example: `./llm.py --folder ./tests/data/dashboards/`
* `./grafana_analysis.py --help` - extracts Prometheus expressions from Grafana dashboards
  Example: `./grafana_analysis.py grafana-report --folder ./tests/data/dashboards/ -c node_exporter`

### Report Examples

Use `pytest tests/calculator/test_sizing_report.py -svv` to create sample sizing reports from small test data.
