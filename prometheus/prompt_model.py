from pathlib import Path
from typing import List

from pydantic import BaseModel


class Target(BaseModel):
    # original expression with labels
    expr: str = None


class PromQuery(Target):
    """Shared by
       1. definition of SLAs (json)
       2. extracting prom expressions from Grafana dashboards
       3. Preparing prompts for LLM
    """
    # labels replaced and static labels extracted
    query: str
    labels: List[str] = []
    staticLabels: List[str] = []


class Title(BaseModel):
    name: str
    queries: List[PromQuery] = []


class PortalPromQuery(PromQuery):
    """Adds connection with Prometheus' expressions to Snowflake table column"""
    rateInterval: str = None
    columnName: str = None


class PromptExample(BaseModel):
    fileName: Path
    titles: List[Title] = []

    def file_names(self) -> List[str]:
        """fill file names for df column"""
        return [self.fileName.parts[-1]] * len(self.titles) if self.fileName else []
