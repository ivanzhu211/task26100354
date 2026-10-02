# task26100354

语义层查询编译器：把面向业务概念的分析查询编译为 SQLite SQL 并执行，
跨一对多关系聚合时不重复计数。纯 Python 标准库（`sqlite3`），无外部依赖。

## 结构

- `semantic_layer/model.py` — 语义模型：概念（表、主键、属性）与多对一关系，
  添加关系时校验无环、任意两概念间至多一条路径。
- `semantic_layer/query.py` — 查询结构：度量（sum/avg/min/max/count）、维度、
  可任意嵌套的 AND/OR 过滤条件。
- `semantic_layer/compiler.py` — 编译器：对每个度量，取度量概念、维度概念、
  过滤谓词概念在关系图上的最小子树，以度量概念为根做 LEFT JOIN；
  内层子查询按 (根主键, 维度取值) 去重，保证每行对每组至多贡献一次，
  外层再做聚合。谓词遇 NULL 自然为假（SQL 三值逻辑）。
- `semantic_layer/engine.py` — 执行引擎：每个度量单独编译执行，
  再按维度取值合并；某组缺席的度量取 NULL。

## 用法

```python
import sqlite3
from semantic_layer import (
    Concept, Dimension, Engine, Measure, Or, Predicate, Query,
    Relation, SemanticModel,
)

model = SemanticModel()
model.add_concept(Concept("customer", "customers", "id",
                          {"id": "id", "region": "region"}))
model.add_concept(Concept("order", "orders", "id",
                          {"id": "id", "customer": "customer_id",
                           "amount": "amount"}))
model.add_relation(Relation("order", "customer_id", "customer"))

engine = Engine(model, sqlite3.connect(":memory:"))
rows = engine.execute(Query(
    measures=(Measure("order", "sum", "amount"),),
    dimensions=(Dimension("customer", "region"),),
))
```

## 测试

```
python3 -m unittest discover -s tests -v
```
