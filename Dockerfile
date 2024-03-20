FROM python:3.11 as builder

# ---------------- Install pip packages that will be copied to the app image ----------------
COPY pyproject.toml poetry.lock ./

# Python packages are installed system-wide, root privileges required
USER 0
RUN python -m pip install --upgrade --no-cache-dir pip setuptools poetry

RUN python -m poetry export --without-hashes -f requirements.txt -o requirements.txt
# Install via pip because we can select target location - https://github.com/python-poetry/poetry/issues/1937
# ignore-installed - poetry has some of our dependencies, they wouldn't be installed to the target location otherwise
RUN python -m pip install --no-cache-dir --ignore-installed --prefix /build/packages -r requirements.txt
USER 2001
