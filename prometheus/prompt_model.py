from pathlib import Path
from typing import List

from pydantic import BaseModel


class Target(BaseModel):
    # original expression with labels
    expr: str = None


class PromExpression(Target):
    """Shared by
       1. definition of SLAs (json)
       2. extracting prom expressions from Grafana dashboards
       3. Preparing prompts for LLM
    """
    # labels replaced and static labels extracted
    query: str
    labels: List[str] = []
    staticLabels: List[str] = []


class ColumnPromExpression(PromExpression):
    """
    Adds connection between (Snowflake) table column and Prometheus' expressions
    tableName is loaded to SlaTable
    """
    # rate interval can be set differently for each expression
    rateInterval: str = None
    columnName: str = None


class Title(BaseModel):
    """Grafana dashboard title with list of Prometheus expressions"""
    name: str
    queries: List[PromExpression] = []


class PromptExample(BaseModel):
    fileName: Path
    titles: List[Title] = []

    def file_names(self) -> List[str]:
        """fill file names for df column"""
        return [self.fileName.parts[-1]] * len(self.titles) if self.fileName else []
