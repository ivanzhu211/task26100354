"""查询执行：逐度量编译执行，再按维度取值合并结果组。"""

from semantic_compiler import compile_measure


def execute(model, conn, measures, dimensions, filter_=None):
    """执行查询，返回 [{"dims": tuple, "measures": tuple}, ...]。"""
    n_dims = len(dimensions)
    groups = {}
    order = []
    for i, measure in enumerate(measures):
        sql, params = compile_measure(model, measure, dimensions, filter_)
        for row in conn.execute(sql, params):
            key = tuple(row[:n_dims])
            if key not in groups:
                groups[key] = [None] * len(measures)
                order.append(key)
            groups[key][i] = row[n_dims]
    return [{"dims": key, "measures": tuple(groups[key])} for key in order]
