"""手工小数据上的端到端测试，与手算结果比对。

数据（客户、订单、预约；订单和预约都多对一指向客户）：

customers: id, region, ltv
  1 east 1000
  2 east 500
  3 west NULL
  4 west 100      -- 没有任何订单和预约

orders: id, customer_id, amount, channel
  10 1 100  web
  11 1 200  store
  12 2 50   web
  13 3 NULL web     -- NULL 金额

appointments: id, customer_id, status
  20 1 cancelled
  21 1 done
  22 2 done
  23 3 cancelled
  24 3 cancelled
  25 2 NULL         -- NULL 状态
"""
from __future__ import annotations

import sqlite3
import unittest

from semantic_layer import (
    And,
    Concept,
    Dimension,
    Engine,
    Measure,
    Or,
    Predicate,
    Query,
    Relation,
    SemanticModel,
)


def build_model() -> SemanticModel:
    model = SemanticModel()
    model.add_concept(Concept(
        "customer", "customers", "id",
        {"id": "id", "region": "region", "ltv": "ltv"},
    ))
    model.add_concept(Concept(
        "order", "orders", "id",
        {"id": "id", "customer": "customer_id", "amount": "amount",
         "channel": "channel"},
    ))
    model.add_concept(Concept(
        "appointment", "appointments", "id",
        {"id": "id", "customer": "customer_id", "status": "status"},
    ))
    model.add_relation(Relation("order", "customer_id", "customer"))
    model.add_relation(Relation("appointment", "customer_id", "customer"))
    return model


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT, ltv INTEGER);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER,
            channel TEXT
        );
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT
        );
        INSERT INTO customers VALUES
            (1, 'east', 1000), (2, 'east', 500), (3, 'west', NULL),
            (4, 'west', 100);
        INSERT INTO orders VALUES
            (10, 1, 100, 'web'), (11, 1, 200, 'store'),
            (12, 2, 50, 'web'), (13, 3, NULL, 'web');
        INSERT INTO appointments VALUES
            (20, 1, 'cancelled'), (21, 1, 'done'), (22, 2, 'done'),
            (23, 3, 'cancelled'), (24, 3, 'cancelled'), (25, 2, NULL);
        """
    )
    return conn


def as_dict(rows):
    return {r.dims: r.values for r in rows}


class Scenario1Test(unittest.TestCase):
    """度量在客户上，维度落在订单上（一对多方向）。"""

    def setUp(self):
        self.engine = Engine(build_model(), build_conn())

    def test_count_customer_by_order_channel(self):
        # 手算：
        #   c1 有订单 (web, store) -> 进 web、store 两组
        #   c2 有订单 (web)        -> 进 web
        #   c3 有订单 (web)        -> 进 web
        #   c4 无订单              -> 维度取 NULL 组
        # count: web=3, store=1, NULL=1
        # sum(ltv): web=1000+500=1500(c3 的 ltv 为 NULL 不计),
        #           store=1000, NULL=100
        rows = self.engine.execute(Query(
            measures=(
                Measure("customer", "count", name="cnt"),
                Measure("customer", "sum", "ltv", name="ltv"),
            ),
            dimensions=(Dimension("order", "channel"),),
        ))
        self.assertEqual(as_dict(rows), {
            ("web",): (3, 1500),
            ("store",): (1, 1000),
            (None,): (1, 100),
        })

    def test_avg_and_max_customer_by_channel(self):
        # avg(ltv): web=(1000+500)/2=750, store=1000, NULL=100
        # max(ltv): web=1000, store=1000, NULL=100
        rows = self.engine.execute(Query(
            measures=(
                Measure("customer", "avg", "ltv"),
                Measure("customer", "max", "ltv"),
            ),
            dimensions=(Dimension("order", "channel"),),
        ))
        self.assertEqual(as_dict(rows), {
            ("web",): (750.0, 1000),
            ("store",): (1000.0, 1000),
            (None,): (100.0, 100),
        })


class Scenario2Test(unittest.TestCase):
    """按客户地区分组，sum(订单金额) + count(预约)，
    过滤：预约状态 = cancelled OR 订单渠道 = web。"""

    def setUp(self):
        self.engine = Engine(build_model(), build_conn())
        self.filter = Or((
            Predicate("appointment", "status", "=", "cancelled"),
            Predicate("order", "channel", "=", "web"),
        ))

    def test_sum_amount_by_region(self):
        # 手算（每个订单行，关联其客户的所有预约）：
        #   o10 (c1,100,web)   渠道 web -> 通过          -> east
        #   o11 (c1,200,store) c1 有 cancelled 预约 -> 通过 -> east
        #   o12 (c2,50,web)    渠道 web -> 通过          -> east
        #   o13 (c3,NULL,web)  渠道 web -> 通过,金额为 NULL -> west
        # east = 100+200+50 = 350；west 只有 NULL 金额 -> SUM 为 NULL
        rows = self.engine.execute(Query(
            measures=(Measure("order", "sum", "amount"),),
            dimensions=(Dimension("customer", "region"),),
            filter=self.filter,
        ))
        self.assertEqual(as_dict(rows), {
            ("east",): (350,),
            ("west",): (None,),
        })

    def test_count_appointment_by_region(self):
        # 手算（每个预约行，关联其客户的所有订单）：
        #   a20 (c1,cancelled) 状态命中            -> east
        #   a21 (c1,done)      c1 有 web 订单      -> east
        #   a22 (c2,done)      c2 有 web 订单      -> east
        #   a23 (c3,cancelled) 状态命中            -> west
        #   a24 (c3,cancelled) 状态命中            -> west
        #   a25 (c2,NULL)      NULL 谓词为假，
        #                      但 c2 有 web 订单   -> east
        # east=4, west=2
        rows = self.engine.execute(Query(
            measures=(Measure("appointment", "count"),),
            dimensions=(Dimension("customer", "region"),),
            filter=self.filter,
        ))
        self.assertEqual(as_dict(rows), {
            ("east",): (4,),
            ("west",): (2,),
        })

    def test_two_measures_merged(self):
        # 两个度量合并：与各自单独查询完全一致
        rows = self.engine.execute(Query(
            measures=(
                Measure("order", "sum", "amount"),
                Measure("appointment", "count"),
            ),
            dimensions=(Dimension("customer", "region"),),
            filter=self.filter,
        ))
        self.assertEqual(as_dict(rows), {
            ("east",): (350, 4),
            ("west",): (None, 2),
        })

    def test_group_missing_in_one_measure_gets_null(self):
        # 过滤只留 cancelled 预约：没有订单渠道谓词，
        # 使部分组在某个度量中缺席时其余度量取 NULL。
        filt = Predicate("appointment", "status", "=", "cancelled")
        rows = self.engine.execute(Query(
            measures=(
                Measure("appointment", "count"),
                Measure("order", "sum", "amount"),
            ),
            dimensions=(Dimension("customer", "region"),),
            filter=filt,
        ))
        # count(预约): east: a20 -> 1; west: a23,a24 -> 2
        # sum(金额): 订单需其客户有 cancelled 预约:
        #   o10(c1),o11(c1) -> east 300; o13(c3,NULL) -> west NULL
        #   o12(c2) 无 cancelled 预约 -> 不进任何组
        self.assertEqual(as_dict(rows), {
            ("east",): (1, 300),
            ("west",): (2, None),
        })

    def test_and_or_nesting(self):
        # (状态 = cancelled OR 渠道 = web) AND 地区 = east
        filt = And((
            Or((
                Predicate("appointment", "status", "=", "cancelled"),
                Predicate("order", "channel", "=", "web"),
            )),
            Predicate("customer", "region", "=", "east"),
        ))
        rows = self.engine.execute(Query(
            measures=(Measure("order", "sum", "amount"),),
            dimensions=(Dimension("customer", "region"),),
            filter=filt,
        ))
        self.assertEqual(as_dict(rows), {("east",): (350,)})


if __name__ == "__main__":
    unittest.main()
