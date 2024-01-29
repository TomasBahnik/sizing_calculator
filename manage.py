"""Command-line utilities for managing the application and its infrastructure."""

from __future__ import annotations

import typer


app = typer.Typer()


@app.command()
def lint():
    """Run linting check."""
    import flake8.main.application

    linter = flake8.main.application.Application()
    linter.run(["."])

    return 1 if linter.result_count else 0


@app.command()
def format():
    """Automatically format code with Black and sort imports with isort."""
    from subprocess import call

    # Run black to automatically format code and check for errors
    black_errors = call(["black", "."])

    # Run isort to automatically sort imports and check for errors
    isort_errors = call(["isort", "."])

    # Return 1 if there were any errors, 0 otherwise
    return 1 if black_errors or isort_errors else 0


if __name__ == "__main__":
    app()
