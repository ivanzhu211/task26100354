"""分析查询的结构定义：度量、维度、过滤条件 AST。"""

AGGREGATES = ("sum", "avg", "min", "max", "count")


class Measure:
    """度量：某概念某属性上的 sum/avg/min/max，或某概念的 count（行数）。"""

    def __init__(self, concept, agg, attribute=None):
        self.concept = concept
        self.agg = agg
        self.attribute = attribute


class Dimension:
    """维度：某概念的一个属性。"""

    def __init__(self, concept, attribute):
        self.concept = concept
        self.attribute = attribute


class Predicate:
    """比较谓词：某概念的属性与常量比较。"""

    def __init__(self, concept, attribute, op, value):
        self.concept = concept
        self.attribute = attribute
        self.op = op
        self.value = value


class And:
    def __init__(self, *parts):
        self.parts = parts


class Or:
    def __init__(self, *parts):
        self.parts = parts
