FROM python:3.11

# Set up the project directory
WORKDIR /app

# Copy poetry files
COPY poetry.lock pyproject.toml /app/

# Install Poetry via pip
RUN pip install poetry==1.5.1

# Install dependencies
RUN poetry install

# Copy the rest of the application
COPY . /app

# Use poetry run INSIDE app folder so it uses created virtual env
# and dependecies in it
CMD ["poetry", "run", "python", "main.py", "--help"]
