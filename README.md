## Setting Up

PyCharm on fresh WSL2 does not render markdown preview. PyCharm relies on JavaFX for rendering Markdown previews. WSL2
does not support GUI applications natively, so rendering might fail.

```shell
sudo apt update
sudo apt install openjfx
```

[Poetry installation](https://python-poetry.org/docs/#installing-with-the-official-installer)

```shell
curl -sSL https://install.python-poetry.org | python3 -
```

Add `export PATH="/home/toba/.local/bin:$PATH"` to your shell configuration file

[Miniforge](https://github.com/conda-forge/miniforge) (Miniconda is not free for commercial since 2020)
Miniforge3 will now be installed into this location`/home/toba/miniforge3`

If you'd prefer that conda's base environment not be activated on startup, run the following command when conda is
activated:

`conda config --set auto_activate_base false`

You can undo this by running `conda init --reverse $SHELL`? [yes|no]

## Resource Analysis and Sizing

* Collects and analyses [Prometheus](https://prometheus.io/) metrics
* Estimates sizing of container resources for k8s deployment under given workload
* Contains example of LLM API prompt engineering based on [LangChain](https://www.langchain.com/) for
  generating Prometheus expressions from Grafana dashboards

### Install and test

```shell
export venv=sizing_calculator
conda deactivate
conda env remove --name $venv
conda create --name $venv -c conda-forge python=3.12
conda activate $venv

# https://python-poetry.org/docs/#installing-with-the-official-installer
# Poetry should always be installed in a dedicated virtual environment to isolate it 
# from the rest of your system. 
# It should in no case be installed in the environment of the project that is to be managed by Poetry
# If you do not want to install the current project use --no-root.
poetry install --no-root
pytest -svv
```

There is deprecation warning `DeprecationWarning: datetime.datetime.utcfromtimestamp()` from `dateutils`.

```shell
poetry update python-dateutil
```

fixes that

```text
Updating python-dateutil (2.8.2 -> 2.9.0.post0)
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
