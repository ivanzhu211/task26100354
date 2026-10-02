"""语义模型定义：概念、属性、关系。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    """一个业务概念，对应一张表。"""
    name: str
    table: str
    pk: str
    attributes: dict[str, str]  # 属性名 -> 列名


@dataclass(frozen=True)
class Relation:
    """多对一关系：from_concept.fk_column 指向 to_concept 的主键。"""
    from_concept: str
    fk_column: str
    to_concept: str


class SemanticModel:
    """语义模型：概念集合 + 无环关系图。"""

    def __init__(self) -> None:
        self.concepts: dict[str, Concept] = {}
        self.relations: list[Relation] = []

    def add_concept(self, concept: Concept) -> None:
        if concept.name in self.concepts:
            raise ValueError(f"duplicate concept: {concept.name}")
        if concept.pk not in concept.attributes.values():
            raise ValueError(f"pk {concept.pk} must be one of the columns")
        self.concepts[concept.name] = concept

    def add_relation(self, relation: Relation) -> None:
        for name in (relation.from_concept, relation.to_concept):
            if name not in self.concepts:
                raise ValueError(f"unknown concept: {name}")
        src = self.concepts[relation.from_concept]
        if relation.fk_column not in src.attributes.values():
            raise ValueError(f"fk {relation.fk_column} not a column of {src.name}")
        if self._path(relation.from_concept, relation.to_concept) is not None:
            raise ValueError("relation would create a cycle or second path")
        self.relations.append(relation)

    def concept(self, name: str) -> Concept:
        return self.concepts[name]

    def neighbors(self, name: str) -> list[tuple[str, Relation, bool]]:
        """返回 (相邻概念, 关系, 是否为正向(from->to)) 列表。"""
        out: list[tuple[str, Relation, bool]] = []
        for rel in self.relations:
            if rel.from_concept == name:
                out.append((rel.to_concept, rel, True))
            elif rel.to_concept == name:
                out.append((rel.from_concept, rel, False))
        return out

    def _path(self, start: str, goal: str) -> list[str] | None:
        """无向 BFS 找唯一路径，返回概念名序列；不连通返回 None。"""
        if start == goal:
            return [start]
        prev: dict[str, str | None] = {start: None}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            for nxt, _rel, _fwd in self.neighbors(cur):
                if nxt in prev:
                    continue
                prev[nxt] = cur
                if nxt == goal:
                    path = [goal]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])  # type: ignore[arg-type]
                    path.reverse()
                    return path
                queue.append(nxt)
        return None
