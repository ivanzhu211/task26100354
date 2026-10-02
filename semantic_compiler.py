"""把单个度量（含共享的维度与过滤条件）编译为一条 SQLite SQL。"""

from semantic_query import And, Or, Predicate


def _filter_concepts(filter_, acc):
    if filter_ is None:
        return acc
    if isinstance(filter_, Predicate):
        acc.add(filter_.concept)
    else:
        for part in filter_.parts:
            _filter_concepts(part, acc)
    return acc


def _compile_filter(filter_, model, aliases, params):
    if isinstance(filter_, Predicate):
        concept = model.concepts[filter_.concept]
        column = concept.attributes[filter_.attribute]
        ref = f'{aliases[filter_.concept]}."{column}"'
        if filter_.value is None and filter_.op in ("=", "=="):
            return f"{ref} IS NULL"
        if filter_.value is None and filter_.op in ("!=", "<>"):
            return f"{ref} IS NOT NULL"
        params.append(filter_.value)
        return f"{ref} {filter_.op} ?"
    if isinstance(filter_, And):
        joiner = " AND "
    elif isinstance(filter_, Or):
        joiner = " OR "
    else:
        raise ValueError(f"unknown filter node: {filter_!r}")
    parts = [_compile_filter(p, model, aliases, params) for p in filter_.parts]
    return "(" + joiner.join(parts) + ")"


def compile_measure(model, measure, dimensions, filter_):
    """编译单个度量的分组聚合查询，返回 (sql, params)。"""
    root = measure.concept
    involved = {root}
    for dim in dimensions:
        involved.add(dim.concept)
    _filter_concepts(filter_, involved)

    # 最小连接子树：以 root 到各涉及概念的唯一路径的并集。
    subtree_adj = {c: [] for c in involved}
    for concept in involved:
        if concept == root:
            continue
        for rel, frm, to in model.find_path(root, concept):
            for c in (frm, to):
                subtree_adj.setdefault(c, [])
            subtree_adj[frm].append((to, rel))
            subtree_adj[to].append((frm, rel))

    # 以 root 为根 BFS，分配别名并生成 LEFT JOIN 序列。
    aliases = {root: "t0"}
    joins = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        for neighbor, rel in subtree_adj.get(node, []):
            if neighbor in aliases:
                continue
            alias = f"t{len(aliases)}"
            aliases[neighbor] = alias
            table = model.concepts[neighbor].table
            parent_alias = aliases[node]
            if rel.many_side == neighbor and rel.one_side == node:
                cond = f'{alias}."{rel.fk_column}" = {parent_alias}."{model.concepts[node].pk}"'
            elif rel.many_side == node and rel.one_side == neighbor:
                cond = f'{parent_alias}."{rel.fk_column}" = {alias}."{model.concepts[neighbor].pk}"'
            else:
                raise ValueError("relationship does not connect these concepts")
            joins.append(f'LEFT JOIN "{table}" {alias} ON {cond}')
            queue.append(neighbor)

    root_concept = model.concepts[root]
    root_alias = aliases[root]
    select_cols = [f'{root_alias}."{root_concept.pk}" AS pk']
    if measure.agg != "count":
        mcol = root_concept.attributes[measure.attribute]
        select_cols.append(f'{root_alias}."{mcol}" AS mval')
    for i, dim in enumerate(dimensions):
        dcol = model.concepts[dim.concept].attributes[dim.attribute]
        select_cols.append(f'{aliases[dim.concept]}."{dcol}" AS d{i}')

    params = []
    sql_parts = [
        "SELECT DISTINCT " + ", ".join(select_cols),
        f'FROM "{root_concept.table}" {root_alias}',
    ]
    sql_parts.extend(joins)
    if filter_ is not None:
        sql_parts.append("WHERE " + _compile_filter(filter_, model, aliases, params))
    inner = "\n".join(sql_parts)

    dim_names = [f"d{i}" for i in range(len(dimensions))]
    if measure.agg == "count":
        agg_expr = "COUNT(*)"
    else:
        agg_expr = f"{measure.agg.upper()}(mval)"
    outer_select = dim_names + [f"{agg_expr} AS v"]
    outer = f"SELECT {', '.join(outer_select)} FROM (\n{inner}\n)"
    if dim_names:
        outer += " GROUP BY " + ", ".join(dim_names)
        outer += " ORDER BY " + ", ".join(dim_names)
    return outer, params
