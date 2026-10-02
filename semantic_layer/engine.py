"""查询执行引擎：编译、执行、按维度组合并多度量结果。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .model import SemanticModel
from .query import Query
from .compiler import compile_measure


@dataclass(frozen=True)
class ResultRow:
    """一个结果组：维度取值 + 各度量值。"""
    dims: tuple[Any, ...]
    values: tuple[Any, ...]


class Engine:
    def __init__(self, model: SemanticModel, conn: sqlite3.Connection) -> None:
        self.model = model
        self.conn = conn

    def execute(self, query: Query) -> list[ResultRow]:
        if not query.measures:
            raise ValueError("query must have at least one measure")
        # 每个度量单独编译执行，再按维度取值合并；缺失的度量取 NULL
        merged: dict[tuple[Any, ...], list[Any]] = {}
        order: list[tuple[Any, ...]] = []
        for idx, measure in enumerate(query.measures):
            compiled = compile_measure(
                self.model, measure, query.dimensions, query.filter
            )
            cursor = self.conn.execute(compiled.sql, compiled.params)
            for row in cursor.fetchall():
                dims = tuple(row[: compiled.dim_count])
                value = row[compiled.dim_count]
                if dims not in merged:
                    merged[dims] = [None] * len(query.measures)
                    order.append(dims)
                merged[dims][idx] = value
        return [ResultRow(dims=d, values=tuple(merged[d])) for d in order]
