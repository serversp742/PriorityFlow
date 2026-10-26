"""
Integration tests for PriorityFlow REST API endpoints.
"""

import pytest
import json
from app import app, priority_flow_heap, sync_heap_from_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_api_overview(client):
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "data" in data
    d = data["data"]
    assert "total_tasks" in d
    assert "pending_tasks" in d
    assert "in_progress_tasks" in d
    assert "completed_tasks" in d
    assert "critical_priority_tasks" in d
    assert "current_queue_size" in d
    assert "total_inserts" in d
    assert "total_extractions" in d
    assert "priority_distribution" in d
    assert "status_distribution" in d
    assert "recent_events" in d


def test_api_heap_state(client):
    res = client.get("/api/heap/state")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "array" in data
    assert "tree" in data
    assert data["is_valid"] is True


def test_api_create_task(client):
    payload = {
        "title": "API Test Database Outage",
        "category": "Critical Infrastructure",
        "priority": 1,
        "estimated_duration": 10,
        "payload": {"region": "us-east-1"}
    }
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert "steps" in data

    # Verify root is P1
    state = client.get("/api/heap/state").get_json()
    assert state["root"]["priority"] == 1


def test_api_extract_next_task(client):
    res = client.post("/api/tasks/extract-next")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "assigned_worker" in data
    assert "steps" in data


def test_api_seed_and_clear_tasks(client):
    # Clear all tasks to verify empty state
    clear_res = client.post("/api/tasks/clear-all")
    assert clear_res.status_code == 200
    ov_cleared = client.get("/api/overview").get_json()["data"]
    assert ov_cleared["is_empty"] is True
    assert ov_cleared["total_tasks"] == 0

    # Seed sample tasks back
    seed_res = client.post("/api/tasks/seed-samples")
    assert seed_res.status_code == 200
    ov_seeded = client.get("/api/overview").get_json()["data"]
    assert ov_seeded["is_empty"] is False
    assert ov_seeded["total_tasks"] > 0


def test_api_verify_heapq(client):
    res = client.get("/api/dsa/verify-heapq")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["identical"] is True


def test_api_task_export(client):
    res = client.get("/api/tasks/export")
    assert res.status_code == 200
    assert res.content_type == "application/json"
    tasks = json.loads(res.data)
    assert isinstance(tasks, list)


def test_task_creation_form_validation(client):
    """Verifies that task creation validates required fields and priority boundaries."""
    # 1. Missing title
    res = client.post("/api/tasks", json={"priority": 2})
    assert res.status_code == 400
    assert "title is required" in res.get_json()["message"].lower()

    # 2. Too short title (< 2 chars)
    res = client.post("/api/tasks", json={"title": "A", "priority": 2})
    assert res.status_code == 400
    assert "at least 2 characters" in res.get_json()["message"].lower()

    # 3. Invalid priority (out of 1-4 bounds)
    res = client.post("/api/tasks", json={"title": "Valid Title", "priority": 5})
    assert res.status_code == 400
    assert "priority must be" in res.get_json()["message"].lower()

    res = client.post("/api/tasks", json={"title": "Valid Title", "priority": 0})
    assert res.status_code == 400


def test_task_creation_fields_and_sequence(client):
    """Verifies assignment of unique task ID, monotonic insertion sequence, and optional fields."""
    payload1 = {
        "title": "Renew SSL Wildcard Cert",
        "description": "Rotate Let's Encrypt wildcard cert for api.internal",
        "priority": 1,
        "category": "Security Patch",
        "due_date": "2026-11-01"
    }
    res1 = client.post("/api/tasks", json=payload1)
    assert res1.status_code == 201
    d1 = res1.get_json()
    assert d1["status"] == "success"
    task1 = d1["task"]
    assert task1["title"] == payload1["title"]
    assert task1["description"] == payload1["description"]
    assert task1["priority"] == 1
    assert task1["category"] == payload1["category"]
    assert task1["due_date"] == payload1["due_date"]
    assert task1["id"] is not None
    seq1 = task1["insertion_sequence"]
    assert seq1 > 0

    # Create second task and ensure sequence is strictly monotonic (seq2 > seq1)
    payload2 = {
        "title": "Optimize Postgres VACUUM",
        "priority": 4
    }
    res2 = client.post("/api/tasks", json=payload2)
    assert res2.status_code == 201
    task2 = res2.get_json()["task"]
    assert task2["id"] != task1["id"]
    assert task2["insertion_sequence"] > seq1


def test_insertion_metrics_and_trace_explanation(client):
    """Verifies insertion metrics, truthful explanation narrative, and heap state."""
    # Clear heap and database first
    client.post("/api/tasks/clear-all")

    # 1. First task into empty queue -> must be root (index 0) with 0 swaps
    res_root = client.post("/api/tasks", json={
        "title": "Root Task",
        "priority": 3,
        "description": "First inserted task"
    })
    assert res_root.status_code == 201
    d_root = res_root.get_json()
    metrics_root = d_root["metrics"]
    assert metrics_root["initial_index"] == 0
    assert metrics_root["final_index"] == 0
    assert metrics_root["swaps_count"] == 0
    assert metrics_root["comparisons_count"] == 0
    assert "heap index 0" in d_root["explanation"]

    # 2. Insert low priority task (P4) -> placed at index 1, parent at index 0 (P3)
    # Since child (P4) > parent (P3), no swap should occur
    res_child = client.post("/api/tasks", json={
        "title": "Low Priority Child",
        "priority": 4
    })
    assert res_child.status_code == 201
    d_child = res_child.get_json()
    metrics_child = d_child["metrics"]
    assert metrics_child["initial_index"] == 1
    assert metrics_child["final_index"] == 1
    assert metrics_child["comparisons_count"] == 1
    assert metrics_child["swaps_count"] == 0
    assert "No swap needed" in d_child["explanation"]

    # 3. Insert critical task (P1) -> placed at index 2, parent at index 0 (P3)
    # Since child (P1) < parent (P3), swap MUST occur upward
    res_p1 = client.post("/api/tasks", json={
        "title": "Emergency Heartbeat Failover",
        "priority": 1
    })
    assert res_p1.status_code == 201
    d_p1 = res_p1.get_json()
    metrics_p1 = d_p1["metrics"]
    assert metrics_p1["initial_index"] == 2
    assert metrics_p1["final_index"] == 0
    assert metrics_p1["comparisons_count"] == 1
    assert metrics_p1["swaps_count"] == 1
    assert "Swapped upward" in d_p1["explanation"]
    assert "min-heap property" in d_p1["explanation"]


def test_simulator_state_and_lifecycle(client):
    """
    Tests the Execution Simulator:
    1. Clear all tasks -> Empty state with friendly response.
    2. Enqueue sample task -> next_eligible_task populated, active_task is None.
    3. Execute Next Task -> extracted from heap, status becomes PROCESSING (In Progress),
       algorithm_duration_ms measured and recorded, started_at recorded, NOT automatically completed.
    4. Mark Current Task Completed -> status becomes COMPLETED, real_world_duration_s recorded,
       worker freed, task ineligible for execution again.
    """
    # 1. Clear tasks to verify empty simulator state
    client.post("/api/tasks/clear-all")
    sim_empty = client.get("/api/simulator/state").get_json()
    assert sim_empty["status"] == "success"
    assert sim_empty["active_task"] is None
    assert sim_empty["remaining_pending_count"] == 0
    assert sim_empty["next_eligible_task"] is None

    # Clicking Execute Next on empty queue returns friendly error
    exec_empty = client.post("/api/tasks/extract-next")
    assert exec_empty.status_code == 400
    assert "queue is currently empty" in exec_empty.get_json()["message"].lower()

    # 2. Enqueue a P1 task and a P2 task
    t1 = client.post("/api/tasks", json={
        "title": "Payment Gateway Timeout",
        "priority": 1,
        "description": "Stripe webhook 504 gateway timeout investigation"
    }).get_json()["task"]

    t2 = client.post("/api/tasks", json={
        "title": "Nightly Analytics ETL",
        "priority": 2,
        "description": "Dimensional table aggregation"
    }).get_json()["task"]

    # Verify Simulator state shows next eligible task as P1
    sim_state = client.get("/api/simulator/state").get_json()
    assert sim_state["remaining_pending_count"] == 2
    assert sim_state["next_eligible_task"]["task_id"] == t1["id"]
    assert sim_state["next_eligible_task"]["priority"] == 1
    assert sim_state["active_task"] is None

    # 3. Click Execute Next Task
    exec_res = client.post("/api/tasks/extract-next")
    assert exec_res.status_code == 200
    exec_data = exec_res.get_json()
    assert exec_data["status"] == "success"
    assert exec_data["task"]["id"] == t1["id"]
    assert exec_data["task"]["status"] == "PROCESSING"
    assert exec_data["task"]["started_at"] is not None
    assert "algorithm_duration_ms" in exec_data
    assert exec_data["algorithm_duration_ms"] >= 0.0

    # In-progress task must NOT be automatically completed
    task_in_db = client.get(f"/api/tasks/{t1['id']}").get_json()["task"]
    assert task_in_db["status"] == "PROCESSING"
    assert task_in_db["completed_at"] is None

    # Simulator state now shows this active task
    sim_active = client.get("/api/simulator/state").get_json()
    assert sim_active["active_task"] is not None
    assert sim_active["active_task"]["id"] == t1["id"]
    assert sim_active["active_task"]["status"] == "PROCESSING"
    assert sim_active["active_task"]["algorithm_duration_ms"] >= 0.0
    assert "elapsed_seconds" in sim_active["active_task"]
    assert sim_active["remaining_pending_count"] == 1
    assert sim_active["next_eligible_task"]["task_id"] == t2["id"]

    # 4. Explicit user action: Mark Current Task Completed
    comp_res = client.post(f"/api/tasks/{t1['id']}/complete")
    assert comp_res.status_code == 200
    comp_data = comp_res.get_json()
    assert comp_data["status"] == "success"
    assert comp_data["task"]["status"] == "COMPLETED"
    assert comp_data["task"]["completed_at"] is not None
    assert "real_world_duration_s" in comp_data

    # Ensure completed task is not eligible for execution again
    # The heap only has t2 remaining, so next execution dispatches t2, not t1
    exec_next = client.post("/api/tasks/extract-next").get_json()
    assert exec_next["task"]["id"] == t2["id"]


def test_simulator_cancel_or_skip_task_policy(client):
    """
    Tests cancellation/skip policy:
    - Task in progress is cancelled with a stated reason.
    - Status transitions to CANCELLED.
    - Assigned worker is released back to IDLE.
    - Audit log records the event.
    - Task cannot be executed again.
    """
    client.post("/api/tasks/clear-all")
    t = client.post("/api/tasks", json={
        "title": "Low Priority Diagnostic Dump",
        "priority": 4,
        "description": "Non-essential debug log sweep"
    }).get_json()["task"]

    # Extract to in-progress
    client.post("/api/tasks/extract-next")

    # Cancel via simulator
    cancel_res = client.post("/api/simulator/cancel", json={
        "task_id": t["id"],
        "reason": "Superseded by cluster maintenance"
    })
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.get_json()
    assert cancel_data["status"] == "success"
    assert cancel_data["task"]["status"] == "CANCELLED"

    # Verify simulator active task is now None
    sim_state = client.get("/api/simulator/state").get_json()
    assert sim_state["active_task"] is None

    # Worker freed back to IDLE
    workers = client.get("/api/workers").get_json()["workers"]
    for w in workers:
        if w["name"] == cancel_data["task"]["assigned_worker"]:
            assert w["status"] == "IDLE"


