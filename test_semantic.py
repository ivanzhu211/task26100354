# 手工小数据上的端到端测试，结果均与手算比对。
#
# 数据：
#   customers: 1 Alice east visits=5
#              2 Bob   east visits=3
#              3 Carol west visits=7   （无订单、无预约）
#              4 Dave  NULL visits=2   （无订单、无预约）
#   orders:    o1 c1 web   100
#              o2 c1 store 50
#              o3 c2 web   NULL
#              o4 c1 web   20          （同一客户多张 web 订单，验证去重）
#   appointments: a1 c1 cancelled
#                 a2 c1 done
#                 a3 c3 cancelled

import sqlite3
import unittest

from semantic_model import SemanticModel
from semantic_query import And, Dimension, Measure, Or, Predicate
from semantic_engine import execute


def build_model():
    model = SemanticModel()
    model.add_concept(
        "customer", "customers", "id",
        {"name": "name", "region": "region", "visits": "visits"},
    )
    model.add_concept(
        "order", "orders", "id",
        {"channel": "channel", "amount": "amount"},
    )
    model.add_concept(
        "appt", "appointments", "id",
        {"status": "status"},
    )
    model.add_relationship("order", "customer_id", "customer")
    model.add_relationship("appt", "customer_id", "customer")
    return model


def build_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT,
                                region TEXT, visits INTEGER);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER,
                             channel TEXT, amount INTEGER);
        CREATE TABLE appointments (id INTEGER PRIMARY KEY,
                                   customer_id INTEGER, status TEXT);
        """
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?)",
        [(1, "Alice", "east", 5), (2, "Bob", "east", 3),
         (3, "Carol", "west", 7), (4, "Dave", None, 2)],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?)",
        [(1, 1, "web", 100), (2, 1, "store", 50),
         (3, 2, "web", None), (4, 1, "web", 20)],
    )
    conn.executemany(
        "INSERT INTO appointments VALUES (?, ?, ?)",
        [(1, 1, "cancelled"), (2, 1, "done"), (3, 3, "cancelled")],
    )
    return conn


def as_tuples(rows):
    return [(row["dims"], row["measures"]) for row in rows]


class SemanticLayerTest(unittest.TestCase):
    def setUp(self):
        self.model = build_model()
        self.conn = build_db()

    def tearDown(self):
        self.conn.close()

    def test_measure_on_customer_dim_on_order(self):
        # 度量在客户上，维度落在订单上。
        # 手算：按订单渠道分组，每个客户对其名下出现过的每个渠道贡献一次。
        #   Alice -> {web, store}, Bob -> {web}, Carol/Dave -> {NULL}
        #   NULL : count=2 (Carol,Dave), sum(visits)=7+2=9
        #   store: count=1 (Alice),      sum(visits)=5
        #   web  : count=2 (Alice,Bob),  sum(visits)=5+3=8
        rows = execute(
            self.model, self.conn,
            measures=[Measure("customer", "count"),
                      Measure("customer", "sum", "visits")],
            dimensions=[Dimension("order", "channel")],
        )
        self.assertEqual(
            as_tuples(rows),
            [((None,), (2, 9)),
             (("store",), (1, 5)),
             (("web",), (2, 8))],
        )

    def test_region_grouped_sum_and_count_with_or_filter(self):
        # 按客户地区分组：sum(订单金额) + count(预约)，
        # 过滤：预约状态=cancelled OR 订单渠道=web。
        # 手算 sum(orders.amount)（根=订单，元组=订单x客户x其预约）：
        #   o1(web,100)  渠道web -> 计入 east
        #   o2(store,50) c1有cancelled预约 -> 计入 east
        #   o3(web,NULL) 渠道web -> 计入 east（金额NULL被SUM忽略）
        #   o4(web,20)   渠道web -> 计入 east
        #   east: 100+50+20 = 170
        # 手算 count(appointments)（根=预约，元组=预约x客户x其订单）：
        #   a1(cancelled,c1) 状态命中 -> east
        #   a2(done,c1)      c1有web订单 -> east
        #   a3(cancelled,c3) 状态命中 -> west
        #   east: 2, west: 1
        # 合并：east=(170, 2), west=(NULL, 1)。
        filter_ = Or(
            Predicate("appt", "status", "=", "cancelled"),
            Predicate("order", "channel", "=", "web"),
        )
        rows = execute(
            self.model, self.conn,
            measures=[Measure("order", "sum", "amount"),
                      Measure("appt", "count")],
            dimensions=[Dimension("customer", "region")],
            filter_=filter_,
        )
        self.assertEqual(
            as_tuples(rows),
            [(("east",), (170, 2)),
             (("west",), (None, 1))],
        )


if __name__ == "__main__":
    unittest.main()
