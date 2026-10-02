"""查询结构：度量、维度、过滤条件。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AggFunc = Literal["sum", "avg", "min", "max", "count"]
CmpOp = Literal["=", "!=", "<", "<=", ">", ">="]


@dataclass(frozen=True)
class Measure:
    """度量：某概念某属性上的聚合，或某概念的 count。"""
    concept: str
    agg: AggFunc
    attribute: str | None = None  # count 时为 None
    name: str = ""


@dataclass(frozen=True)
class Dimension:
    """维度：某概念的一个属性。"""
    concept: str
    attribute: str


class Filter:
    """过滤条件基类。"""


@dataclass(frozen=True)
class Predicate(Filter):
    """比较谓词：概念属性 与 字面量比较。"""
    concept: str
    attribute: str
    op: CmpOp
    value: Any


@dataclass(frozen=True)
class And(Filter):
    parts: tuple[Filter, ...]


@dataclass(frozen=True)
class Or(Filter):
    parts: tuple[Filter, ...]


@dataclass(frozen=True)
class Query:
    measures: tuple[Measure, ...]
    dimensions: tuple[Dimension, ...] = ()
    filter: Filter | None = None
