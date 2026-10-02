"""语义模型定义：概念、关系与关系图。"""


class Concept:
    """业务概念：对应一张表，单列主键，若干具名属性（属性名 -> 列名）。"""

    def __init__(self, name, table, pk, attributes):
        self.name = name
        self.table = table
        self.pk = pk
        self.attributes = dict(attributes)


class Relationship:
    """多对一关系：many_side 表上的 fk_column 引用 one_side 的主键。"""

    def __init__(self, many_side, fk_column, one_side):
        self.many_side = many_side
        self.fk_column = fk_column
        self.one_side = one_side


class SemanticModel:
    """语义模型：概念集合 + 无环关系图。"""

    def __init__(self):
        self.concepts = {}
        self.relationships = []

    def add_concept(self, name, table, pk, attributes):
        if name in self.concepts:
            raise ValueError(f"duplicate concept: {name}")
        self.concepts[name] = Concept(name, table, pk, attributes)

    def add_relationship(self, many_side, fk_column, one_side):
        for c in (many_side, one_side):
            if c not in self.concepts:
                raise ValueError(f"unknown concept: {c}")
        self.relationships.append(Relationship(many_side, fk_column, one_side))

    def find_path(self, start, goal):
        """在关系图（不计方向）上找 start 到 goal 的唯一路径。"""
        for c in (start, goal):
            if c not in self.concepts:
                raise ValueError(f"unknown concept: {c}")
        # 每步为 (relationship, from_concept, to_concept)，沿遍历方向记录。
        prev = {start: None}
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node == goal:
                break
            for rel in self.relationships:
                if rel.many_side == node:
                    neighbor = rel.one_side
                elif rel.one_side == node:
                    neighbor = rel.many_side
                else:
                    continue
                if neighbor not in prev:
                    prev[neighbor] = (rel, node, neighbor)
                    queue.append(neighbor)
        if goal not in prev:
            raise ValueError(f"no path: {start} -> {goal}")
        path = []
        step = prev[goal]
        while step is not None:
            path.append(step)
            step = prev[step[1]]
        path.reverse()
        return path
