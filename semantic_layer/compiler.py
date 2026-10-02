"""把单个度量 + 维度 + 过滤编译为 SQLite SQL。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .model import SemanticModel
from .query import And, Dimension, Filter, Measure, Or, Predicate


@dataclass(frozen=True)
class CompiledMeasure:
    sql: str
    params: tuple[Any, ...]
    dim_count: int


def compile_measure(
    model: SemanticModel,
    measure: Measure,
    dimensions: tuple[Dimension, ...],
    filter: Filter | None,
) -> CompiledMeasure:
    if measure.agg == "count":
        if measure.attribute is not None:
            raise ValueError("count measure must not have an attribute")
    elif measure.attribute is None:
        raise ValueError(f"{measure.agg} measure requires an attribute")

    root = measure.concept
    model.concept(root)

    # 1. 收集涉及的概念：度量、维度、过滤谓词
    involved: set[str] = {root}
    for dim in dimensions:
        model.concept(dim.concept)
        involved.add(dim.concept)
    if filter is not None:
        for concept in _filter_concepts(filter):
            model.concept(concept)
            involved.add(concept)

    # 2. 最小子树 = 根到各涉及概念唯一路径的并集
    subtree: set[str] = set()
    for target in involved:
        path = model._path(root, target)
        if path is None:
            raise ValueError(f"concepts {root!r} and {target!r} are not connected")
        subtree.update(path)

    # 3. 从根 BFS，为子树中每个概念分配别名并生成 LEFT JOIN
    alias: dict[str, str] = {root: "t0"}
    joins: list[str] = []
    queue: deque[str] = deque([root])
    while queue:
        cur = queue.popleft()
        for nxt, rel, _fwd in model.neighbors(cur):
            if nxt not in subtree or nxt in alias:
                continue
            child_alias = f"t{len(alias)}"
            alias[nxt] = child_alias
            from_alias = alias[rel.from_concept]
            to_alias = alias[rel.to_concept]
            to_pk = model.concept(rel.to_concept).pk
            on = (
                f'"{from_alias}"."{rel.fk_column}"'
                f' = "{to_alias}"."{to_pk}"'
            )
            table = model.concept(nxt).table
            joins.append(f'LEFT JOIN "{table}" "{child_alias}" ON {on}')
            queue.append(nxt)

    # 4. 维度列与过滤条件
    dim_cols: list[str] = []
    for i, dim in enumerate(dimensions):
        col = model.concept(dim.concept).attributes[dim.attribute]
        dim_cols.append(f'"{alias[dim.concept]}"."{col}" AS "d{i}"')

    params: list[Any] = []
    where_sql = ""
    if filter is not None:
        where_sql = " WHERE " + _filter_sql(model, alias, filter, params)

    # 5. 内层按 (根主键, 维度) 去重，外层聚合，保证每行对每组至多贡献一次
    root_concept = model.concept(root)
    inner_select = [f'"t0"."{root_concept.pk}" AS "__pk"']
    if measure.agg != "count":
        mcol = root_concept.attributes[measure.attribute]  # type: ignore[index]
        inner_select.append(f'"t0"."{mcol}" AS "__mval"')
    inner_select.extend(dim_cols)

    inner = (
        f"SELECT DISTINCT {', '.join(inner_select)} "
        f'FROM "{root_concept.table}" "t0" '
        + " ".join(joins)
        + where_sql
    )

    group_cols = [f'"d{i}"' for i in range(len(dimensions))]
    if measure.agg == "count":
        agg_expr = "COUNT(*)"
    else:
        agg_expr = f'{measure.agg.upper()}("__mval")'
    outer_select = group_cols + [f'{agg_expr} AS "value"']
    sql = f"SELECT {', '.join(outer_select)} FROM ({inner})"
    if group_cols:
        sql += f" GROUP BY {', '.join(group_cols)}"

    return CompiledMeasure(sql=sql, params=tuple(params), dim_count=len(dimensions))


def _filter_concepts(filter: Filter) -> set[str]:
    if isinstance(filter, Predicate):
        return {filter.concept}
    if isinstance(filter, (And, Or)):
        out: set[str] = set()
        for part in filter.parts:
            out |= _filter_concepts(part)
        return out
    raise TypeError(f"unknown filter: {filter!r}")


def _filter_sql(
    model: SemanticModel,
    alias: dict[str, str],
    filter: Filter,
    params: list[Any],
) -> str:
    if isinstance(filter, Predicate):
        col = model.concept(filter.concept).attributes[filter.attribute]
        params.append(filter.value)
        return f'"{alias[filter.concept]}"."{col}" {filter.op} ?'
    if isinstance(filter, And):
        joiner = " AND "
    elif isinstance(filter, Or):
        joiner = " OR "
    else:
        raise TypeError(f"unknown filter: {filter!r}")
    parts = [_filter_sql(model, alias, p, params) for p in filter.parts]
    return "(" + joiner.join(parts) + ")"
