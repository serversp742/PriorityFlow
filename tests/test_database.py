"""
Tests for PriorityFlow SQLite Database persistence.
"""

import os
import pytest
import database as db

TEST_DB = "test_priorityflow.db"


@pytest.fixture(autouse=True)
def setup_teardown_db():
    db.init_db(TEST_DB)
    # Clean tables before each test
    conn = db.get_db_connection(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM workers")
    cursor.execute("DELETE FROM heap_audit_logs")
    conn.commit()
    conn.close()
    yield
    # Clean tables after each test
    conn = db.get_db_connection(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM workers")
    cursor.execute("DELETE FROM heap_audit_logs")
    conn.commit()
    conn.close()


def test_create_and_get_task():
    t = db.create_task(
        title="Deploy Auth Microservice",
        category="Security Patch",
        priority=2,
        estimated_duration=15,
        payload={"region": "us-east-1"},
        notes="Urgent rollout",
        db_path=TEST_DB
    )
    assert t["id"] is not None
    assert t["title"] == "Deploy Auth Microservice"
    assert t["status"] == "QUEUED"

    fetched = db.get_task(t["id"], db_path=TEST_DB)
    assert fetched is not None
    assert fetched["title"] == "Deploy Auth Microservice"
    assert fetched["payload"]["region"] == "us-east-1"


def test_worker_assignment_and_completion():
    db.seed_demo_data_if_empty(db_path=TEST_DB)

    t = db.create_task(
        title="Worker Test Task",
        priority=2,
        category="General",
        estimated_duration=10,
        payload={},
        db_path=TEST_DB
    )
    worker = db.get_idle_worker(db_path=TEST_DB)
    assert worker is not None

    # Assign
    db.assign_task_to_worker(t["id"], worker["name"], db_path=TEST_DB)
    updated_t = db.get_task(t["id"], db_path=TEST_DB)
    assert updated_t["status"] == "PROCESSING"
    assert updated_t["assigned_worker"] == worker["name"]

    # Complete
    db.complete_task(t["id"], db_path=TEST_DB)
    completed_t = db.get_task(t["id"], db_path=TEST_DB)
    assert completed_t["status"] == "COMPLETED"
    assert completed_t["completed_at"] is not None


def test_analytics_generation():
    db.seed_demo_data_if_empty(db_path=TEST_DB)
    analytics = db.get_performance_analytics(db_path=TEST_DB)

    assert "status_counts" in analytics
    assert "priority_distribution" in analytics
    assert "avg_latency_by_priority" in analytics
    assert analytics["status_counts"]["queued"] > 0


def test_overview_statistics():
    db.seed_demo_data_if_empty(db_path=TEST_DB)
    stats = db.get_overview_statistics(db_path=TEST_DB)

    assert "total_tasks" in stats
    assert "pending_tasks" in stats
    assert "in_progress_tasks" in stats
    assert "completed_tasks" in stats
    assert "critical_priority_tasks" in stats
    assert "current_queue_size" in stats
    assert "total_inserts" in stats
    assert "total_extractions" in stats
    assert "priority_distribution" in stats
    assert "status_distribution" in stats
    assert "recent_events" in stats
    assert stats["is_empty"] is False
    assert stats["total_tasks"] > 0


def test_clear_and_seed_sample_tasks():
    db.seed_demo_data_if_empty(db_path=TEST_DB)
    stats_before = db.get_overview_statistics(db_path=TEST_DB)
    assert stats_before["total_tasks"] > 0

    # Clear all tasks
    db.clear_all_tasks(db_path=TEST_DB)
    stats_cleared = db.get_overview_statistics(db_path=TEST_DB)
    assert stats_cleared["total_tasks"] == 0
    assert stats_cleared["is_empty"] is True

    # Seed sample tasks back
    db.seed_sample_tasks(db_path=TEST_DB)
    stats_seeded = db.get_overview_statistics(db_path=TEST_DB)
    assert stats_seeded["total_tasks"] > 0
    assert stats_seeded["is_empty"] is False
