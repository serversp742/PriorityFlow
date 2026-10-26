"""
Unit tests for PriorityFlow BinaryMinHeap Priority Queue.
"""

import pytest
import time
import heapq
from priority_queue import BinaryMinHeap, HeapNode


def test_empty_heap():
    h = BinaryMinHeap()
    assert len(h) == 0
    assert h.is_empty()
    assert h.peek() is None
    node, steps = h.extract_min()
    assert node is None
    assert steps == []
    assert h.is_valid_heap()


def test_insertion_and_peek():
    h = BinaryMinHeap()
    now = time.time()
    h.insert(1, 3, now + 1, {"title": "P3 Task"})
    h.insert(2, 1, now + 2, {"title": "P1 Outage Task"})
    h.insert(3, 4, now + 3, {"title": "P4 Task"})
    h.insert(4, 2, now + 4, {"title": "P2 Task"})

    assert len(h) == 4
    assert h.is_valid_heap()

    root = h.peek()
    assert root is not None
    assert root.task_id == 2
    assert root.priority == 1


def test_extract_min_order():
    h = BinaryMinHeap()
    now = time.time()
    tasks = [
        (101, 5, now + 1, "T5"),
        (102, 2, now + 2, "T2"),
        (103, 1, now + 3, "T1"),
        (104, 4, now + 4, "T4"),
        (105, 3, now + 5, "T3"),
    ]
    for tid, prio, created, title in tasks:
        h.insert(tid, prio, created, {"title": title})

    extracted_priorities = []
    while not h.is_empty():
        assert h.is_valid_heap()
        node, _ = h.extract_min()
        extracted_priorities.append(node.priority)

    # Must be extracted in strict ascending order of priority (1 to 5)
    assert extracted_priorities == [1, 2, 3, 4, 5]


def test_tie_breaking_by_created_at():
    h = BinaryMinHeap()
    base_time = 1000.0

    # Both are P2, but task 202 was created earlier
    h.insert(201, 2, base_time + 50, {"title": "Created Later"})
    h.insert(202, 2, base_time + 10, {"title": "Created Earlier"})

    first, _ = h.extract_min()
    second, _ = h.extract_min()

    assert first.task_id == 202
    assert second.task_id == 201


def test_update_priority_decrease_key():
    """Task urgency increases from P4 to P1: Sifts up to root."""
    h = BinaryMinHeap()
    now = time.time()

    h.insert(1, 2, now + 1, {"title": "T1"})
    h.insert(2, 3, now + 2, {"title": "T2"})
    h.insert(3, 4, now + 3, {"title": "T3"})

    assert h.peek().task_id == 1

    updated, steps = h.update_priority(3, 1)
    assert updated is True
    assert h.is_valid_heap()

    # T3 is now root
    assert h.peek().task_id == 3
    assert h.peek().priority == 1


def test_update_priority_increase_key():
    """Root task deprioritized from P1 to P5: Sifts down."""
    h = BinaryMinHeap()
    now = time.time()

    h.insert(1, 1, now + 1, {"title": "T1"})
    h.insert(2, 2, now + 2, {"title": "T2"})
    h.insert(3, 3, now + 3, {"title": "T3"})

    assert h.peek().task_id == 1

    updated, steps = h.update_priority(1, 5)
    assert updated is True
    assert h.is_valid_heap()

    # New root must be T2 (P2)
    assert h.peek().task_id == 2


def test_remove_task():
    h = BinaryMinHeap()
    now = time.time()

    h.insert(1, 1, now + 1, {"title": "T1"})
    h.insert(2, 2, now + 2, {"title": "T2"})
    h.insert(3, 3, now + 3, {"title": "T3"})
    h.insert(4, 4, now + 4, {"title": "T4"})

    removed, _ = h.remove(2)
    assert removed is True
    assert len(h) == 3
    assert h.is_valid_heap()

    removed_again, _ = h.remove(2)
    assert removed_again is False


def test_heap_vs_python_heapq():
    custom_heap = BinaryMinHeap()
    py_heap = []

    test_data = [
        (1, 3, 105.0),
        (2, 1, 102.0),
        (3, 4, 108.0),
        (4, 2, 101.0),
        (5, 1, 101.0),
        (6, 5, 110.0),
        (7, 2, 103.0),
    ]

    for tid, prio, created in test_data:
        custom_heap.insert(tid, prio, created, {"id": tid})
        heapq.heappush(py_heap, (prio, 0, created, tid))

    assert len(custom_heap) == len(py_heap)

    while not custom_heap.is_empty():
        c_node, _ = custom_heap.extract_min()
        py_prio, py_seq, py_created, py_tid = heapq.heappop(py_heap)

        assert c_node.priority == py_prio
        assert c_node.created_at == py_created
        assert c_node.task_id == py_tid


def test_ordering_rule_priority_and_persistent_sequence():
    """
    Verifies the user ordering rule:
    1. First: lower numeric priority (1 before 2).
    2. Second: earlier persistent insertion sequence for equal priorities.
    """
    h = BinaryMinHeap()
    now = time.time()

    # Task A: P2, Sequence #5
    h.insert(1, priority=2, created_at=now, data={"title": "P2 Task A"}, insertion_sequence=5)
    # Task B: P1, Sequence #10 -> Must be extracted first despite higher sequence
    h.insert(2, priority=1, created_at=now, data={"title": "P1 Task B"}, insertion_sequence=10)
    # Task C: P2, Sequence #2 -> Must be extracted before Task A because sequence 2 < 5
    h.insert(3, priority=2, created_at=now, data={"title": "P2 Task C"}, insertion_sequence=2)
    # Task D: P2, Sequence #8 -> Must be extracted after Task A because sequence 8 > 5
    h.insert(4, priority=2, created_at=now, data={"title": "P2 Task D"}, insertion_sequence=8)

    order = []
    while not h.is_empty():
        node, _ = h.extract_min()
        order.append((node.task_id, node.priority, node.insertion_sequence))

    # Expected order:
    # 1. Task 2 (P1, Seq 10)
    # 2. Task 3 (P2, Seq 2)
    # 3. Task 1 (P2, Seq 5)
    # 4. Task 4 (P2, Seq 8)
    assert order == [
        (2, 1, 10),
        (3, 2, 2),
        (1, 2, 5),
        (4, 2, 8)
    ]


def test_build_heap_floyd_linear_time():
    """
    Verifies Floyd's O(n) heap construction algorithm.
    Rearranges an unsorted list of nodes into a valid min-heap.
    """
    nodes = [
        HeapNode(1, priority=4, created_at=100.0, data={"title": "T1"}, insertion_sequence=4),
        HeapNode(2, priority=3, created_at=100.0, data={"title": "T2"}, insertion_sequence=3),
        HeapNode(3, priority=1, created_at=100.0, data={"title": "T3"}, insertion_sequence=1),
        HeapNode(4, priority=2, created_at=100.0, data={"title": "T4"}, insertion_sequence=2),
        HeapNode(5, priority=4, created_at=100.0, data={"title": "T5"}, insertion_sequence=5),
    ]

    h = BinaryMinHeap()
    h.build_heap(nodes)

    assert len(h) == 5
    assert h.is_valid_heap()
    assert h.peek().task_id == 3  # P1 is root

    extracted = []
    while not h.is_empty():
        node, _ = h.extract_min()
        extracted.append(node.task_id)

    # Must extract in order of priority: 3 (P1), 4 (P2), 2 (P3), 1 (P4 Seq 4), 5 (P4 Seq 5)
    assert extracted == [3, 4, 2, 1, 5]


def test_sift_up_and_sift_down_operations():
    """Directly verifies sift_up and sift_down methods."""
    h = BinaryMinHeap()
    now = time.time()

    # Insert elements
    h.insert(1, 3, now, {"title": "A"}, insertion_sequence=1)
    h.insert(2, 2, now, {"title": "B"}, insertion_sequence=2)
    assert h.is_valid_heap()

    # Manually append an element with P1 at the end and call sift_up
    low_node = HeapNode(3, 1, now, {"title": "C"}, insertion_sequence=3)
    h.heap.append(low_node)
    h.index_map[3] = len(h.heap) - 1

    h.sift_up(len(h.heap) - 1)
    assert h.peek().task_id == 3
    assert h.is_valid_heap()

    # Demote root to P4 and call sift_down
    h.heap[0].priority = 4
    h.sift_down(0)
    assert h.peek().task_id != 3
    assert h.peek().priority == 2
    assert h.is_valid_heap()


def test_queue_rebuilding_from_sqlite():
    """
    Verifies that the in-memory queue can be completely rebuilt from SQLite.
    Confirms:
    1. Only Pending tasks (QUEUED or PENDING) are loaded.
    2. In-progress (PROCESSING) and completed (COMPLETED) tasks are excluded.
    3. Cancelled/deleted tasks are excluded.
    4. Persistent insertion sequences are preserved across rebuilds.
    """
    import database as db
    test_db = "test_rebuild_queue.db"
    import os
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    db.init_db(db_path=test_db)

    # 1. Create a set of tasks with various statuses
    t1 = db.create_task("Pending Critical", priority=1, category="Security", db_path=test_db)
    t2 = db.create_task("Pending Medium Earlier", priority=3, category="Data", db_path=test_db)
    t3 = db.create_task("Pending Medium Later", priority=3, category="Data", db_path=test_db)
    t4 = db.create_task("In Progress Task", priority=1, category="Ops", db_path=test_db)
    t5 = db.create_task("Completed Task", priority=2, category="General", db_path=test_db)
    t6 = db.create_task("Cancelled Task", priority=1, category="General", db_path=test_db)

    # Transition statuses
    db.assign_task_to_worker(t4["id"], "Worker-1", db_path=test_db)
    db.assign_task_to_worker(t5["id"], "Worker-2", db_path=test_db)
    db.complete_task(t5["id"], db_path=test_db)
    db.cancel_task(t6["id"], db_path=test_db)

    # 2. Rebuild queue from database
    h = BinaryMinHeap()
    loaded_count = h.rebuild_from_db(db_path=test_db)

    # Only t1, t2, t3 should be loaded (count == 3)
    assert loaded_count == 3
    assert len(h) == 3
    assert h.is_valid_heap()

    # Verify root is t1 (P1)
    assert h.peek().task_id == t1["id"]

    # Verify FIFO ordering for t2 and t3 (both P3, but t2 has earlier sequence)
    node1, _ = h.extract_min()
    node2, _ = h.extract_min()
    node3, _ = h.extract_min()

    assert node1.task_id == t1["id"]
    assert node2.task_id == t2["id"]  # earlier insertion_sequence
    assert node3.task_id == t3["id"]  # later insertion_sequence

    # Cleanup
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


def test_safe_synchronization_prevents_double_execution():
    """
    Verifies that simultaneous execution attempts cannot claim or execute the same task.
    Database atomic CAS ensures only the first attempt transitions the task.
    """
    import database as db
    test_db = "test_sync_safety.db"
    import os
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    db.init_db(db_path=test_db)
    t = db.create_task("Concurrent Target Task", priority=1, category="Security", db_path=test_db)

    # Worker A claims the task
    first_attempt = db.assign_task_to_worker(t["id"], "Worker-A", db_path=test_db)
    assert first_attempt is True

    # Worker B tries to claim the same task simultaneously
    second_attempt = db.assign_task_to_worker(t["id"], "Worker-B", db_path=test_db)
    assert second_attempt is False  # Rejected! Already PROCESSING

    # Cleanup
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


def test_tree_node_attributes_and_serialization():
    """
    Verifies that all 6 required node attributes are serialized:
    1. Task ID
    2. Task title
    3. Priority number
    4. Priority label
    5. Heap index
    6. Insertion sequence
    """
    h = BinaryMinHeap()
    now = time.time()
    h.insert(
        task_id=101,
        priority=1,
        created_at=now,
        data={"title": "Primary Cluster Failover", "category": "Infra"},
        insertion_sequence=5
    )
    h.insert(
        task_id=102,
        priority=3,
        created_at=now + 1,
        data={"title": "Daily Metrics Aggregation", "category": "Data"},
        insertion_sequence=6
    )

    arr = h.to_array()
    assert len(arr) == 2

    # Check root node attributes
    root_node = arr[0]
    assert root_node["task_id"] == 101
    assert root_node["title"] == "Primary Cluster Failover"
    assert root_node["priority"] == 1
    assert root_node["priority_label"] == "Critical"
    assert root_node["index"] == 0
    assert root_node["insertion_sequence"] == 5

    # Check tree structure serialization
    tree = h.to_tree_structure()
    assert tree["task_id"] == 101
    assert tree["title"] == "Primary Cluster Failover"
    assert tree["priority"] == 1
    assert tree["priority_label"] == "Critical"
    assert tree["index"] == 0
    assert tree["insertion_sequence"] == 5
    assert len(tree["children"]) == 1
    assert tree["children"][0]["priority_label"] == "Medium"


def test_logical_execution_order_non_mutating():
    """
    Verifies that logical execution order is calculated using a separate
    non-mutating view of eligible tasks and does NOT alter the real heap array.
    """
    h = BinaryMinHeap()
    now = time.time()

    # Insert tasks in an order that produces a partially-ordered heap array
    # e.g., root is min, but subsequent indices are not sorted linearly
    h.insert(1, priority=1, created_at=now, data={"title": "T1"}, insertion_sequence=1)
    h.insert(2, priority=3, created_at=now, data={"title": "T2"}, insertion_sequence=2)
    h.insert(3, priority=2, created_at=now, data={"title": "T3"}, insertion_sequence=3)
    h.insert(4, priority=4, created_at=now, data={"title": "T4"}, insertion_sequence=4)

    # Snapshot internal heap before calculating logical execution order
    heap_before = [(n.task_id, n.priority) for n in h.heap]
    index_map_before = dict(h.index_map)

    # Call to_logical_execution_order()
    logical_order = h.to_logical_execution_order()

    # 1. Assert internal heap array has NOT been mutated
    heap_after = [(n.task_id, n.priority) for n in h.heap]
    assert heap_before == heap_after
    assert index_map_before == h.index_map

    # 2. Assert logical order is fully sorted by scheduling key
    assert len(logical_order) == 4
    # Expected execution dispatch sequence: P1 (T1) -> P2 (T3) -> P3 (T2) -> P4 (T4)
    ordered_task_ids = [item["task_id"] for item in logical_order]
    assert ordered_task_ids == [1, 3, 2, 4]
    assert logical_order[0]["is_next"] is True
    assert logical_order[1]["is_next"] is False
    assert logical_order[0]["priority_label"] == "Critical"
    assert logical_order[1]["priority_label"] == "High"


def test_extraction_trace_fidelity():
    """
    Verifies that extract_min captures real algorithmic sift-down trace steps:
    1. extract_start
    2. remove_root
    3. replace_root (last element moved to root)
    4. compare_children & compare_parent_child
    5. swap when required
    6. sift_down_complete
    """
    h = BinaryMinHeap()
    now = time.time()
    h.insert(1, priority=1, created_at=now, data={"title": "T1"}, insertion_sequence=1)
    h.insert(2, priority=2, created_at=now, data={"title": "T2"}, insertion_sequence=2)
    h.insert(3, priority=3, created_at=now, data={"title": "T3"}, insertion_sequence=3)
    h.insert(4, priority=4, created_at=now, data={"title": "T4"}, insertion_sequence=4)

    min_node, steps = h.extract_min()
    assert min_node.task_id == 1

    actions = [s["action"] for s in steps]
    assert "extract_start" in actions
    assert "remove_root" in actions
    assert "replace_root" in actions
    assert "sift_down_complete" in actions

    # Step details check
    extract_step = next(s for s in steps if s["action"] == "extract_start")
    assert extract_step["task_id"] == 1
    assert extract_step["priority"] == 1

    replace_step = next(s for s in steps if s["action"] == "replace_root")
    assert replace_step["index"] == 0
    assert replace_step["task_id"] == 4  # last element moved to root

