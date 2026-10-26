"""
PriorityFlow - SQLite Database Persistence Layer
=================================================
Manages storage for:
- Tasks (queued, processing, completed, cancelled) with:
  - Task title (required)
  - Description (optional)
  - Priority: 1 (Critical), 2 (High), 3 (Medium), 4 (Low)
  - Category (optional)
  - Due date (optional)
  - Unique Task ID (auto-assigned)
  - Persistent insertion sequence number (auto-assigned)
- Execution Workers (Node Alpha, Beta, Gamma, Delta)
- Heap Operation Audit Logs
- Analytical Queries and Overview Metrics
"""

import sqlite3
import json
import time
from typing import Any, Dict, List, Optional

DB_FILE = "priorityflow.db"


def get_db_connection(db_path: str = DB_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_FILE):
    """Initializes tables for PriorityFlow and runs safe schema migrations."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT NOT NULL DEFAULT 'General',
        priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
        due_date TEXT DEFAULT '',
        insertion_sequence INTEGER NOT NULL DEFAULT 1,
        estimated_duration INTEGER DEFAULT 12,
        payload TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'QUEUED' CHECK(status IN ('QUEUED', 'PROCESSING', 'COMPLETED', 'CANCELLED')),
        created_at REAL NOT NULL,
        started_at REAL,
        completed_at REAL,
        assigned_worker TEXT,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        region TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'IDLE' CHECK(status IN ('IDLE', 'BUSY', 'OFFLINE')),
        current_task_id INTEGER,
        completed_count INTEGER DEFAULT 0,
        FOREIGN KEY(current_task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS heap_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation TEXT NOT NULL,
        task_id INTEGER,
        details TEXT,
        timestamp REAL NOT NULL
    );
    """)

    # Safe column migrations if existing database table was created with earlier schema
    cursor.execute("PRAGMA table_info(tasks)")
    existing_cols = {col["name"] for col in cursor.fetchall()}

    if "description" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT ''")
    if "due_date" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT DEFAULT ''")
    if "insertion_sequence" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN insertion_sequence INTEGER DEFAULT 1")
    if "algorithm_duration_ms" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN algorithm_duration_ms REAL DEFAULT 0.0")
    if "real_world_duration_s" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN real_world_duration_s REAL DEFAULT 0.0")

    conn.commit()
    conn.close()


def seed_demo_data_if_empty(db_path: str = DB_FILE):
    """Seeds default cloud workers and realistic enterprise tasks if empty."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM workers")
    if cursor.fetchone()["count"] == 0:
        workers = [
            ("Worker Node Alpha-01", "us-east-1 (N. Virginia)", "IDLE", 14),
            ("Worker Node Beta-02", "eu-central-1 (Frankfurt)", "IDLE", 11),
            ("Worker Node Gamma-03", "ap-southeast-1 (Singapore)", "IDLE", 19),
            ("Worker Node Delta-04", "us-west-2 (Oregon)", "IDLE", 8),
        ]
        cursor.executemany(
            "INSERT INTO workers (name, region, status, completed_count) VALUES (?, ?, ?, ?)",
            workers
        )

    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    needs_seed = (cursor.fetchone()["count"] == 0)
    conn.commit()
    conn.close()

    if needs_seed:
        seed_sample_tasks(db_path=db_path)


def seed_sample_tasks(db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    """Seeds a rich set of realistic cloud enterprise tasks."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    base_time = time.time() - 1800

    tasks = [
        # 1 = Critical
        ("Database Primary Replica Failover",
         "Master database unresponsive. Immediate failover required to restore read/write access.",
         "Critical Infrastructure", 1, "2026-10-27", 1, 8,
         json.dumps({"cluster": "db-prod-cluster-01", "retries": 0}), "QUEUED",
         base_time + 400, "Automated high-priority failover triggered by health check"),

        # 2 = High
        ("Stripe Webhook Gateway Reconciliation",
         "Reconcile unmatched subscription invoices before daily billing cutoff.",
         "Payment Gateway", 2, "2026-10-28", 2, 14,
         json.dumps({"batch_id": "stripe-rec-9821", "records": 4820}), "QUEUED",
         base_time + 150, "SLA risk: Reconcile unmatched subscription invoices"),

        # 2 = High
        ("Zero-Day OpenSSL Security Patch Deployment",
         "Hotpatching CVE-2026-1184 across all ingress edge proxy gateways.",
         "Security Patch", 2, "2026-10-27", 3, 20,
         json.dumps({"cve": "CVE-2026-1184", "nodes": 32}), "QUEUED",
         base_time + 320, "Hotpatching ingress edge proxies"),

        # 3 = Medium
        ("ETL Data Pipeline: Daily Revenue Aggregation",
         "Scheduled batch aggregation for corporate executive telemetry dashboards.",
         "Data Pipeline", 3, "2026-10-29", 4, 25,
         json.dumps({"table": "analytics_daily_rev", "format": "parquet"}), "QUEUED",
         base_time + 100, "Daily scheduled warehouse transformation"),

        # 3 = Medium
        ("Generate Enterprise Audit Compliance PDF",
         "Quarterly SOC2 compliance report export for enterprise tenant.",
         "Background Job", 3, "2026-10-31", 5, 18,
         json.dumps({"tenant_id": "tenant-corp-acme", "pages": 140}), "QUEUED",
         base_time + 500, "Quarterly SOC2 compliance report export"),

        # 4 = Low
        ("ElasticSearch Index Re-sharding & Optimization",
         "Background shard re-balancing across replica search cluster.",
         "Search Cluster", 4, "2026-11-05", 6, 30,
         json.dumps({"index": "customer_logs_2026", "shards": 12}), "QUEUED",
         base_time + 200, "Background shard re-balancing"),

        # 4 = Low
        ("Cold Storage S3 Glacier Log Compression",
         "Routine monthly archival compression for raw telemetry logs.",
         "Storage & Archival", 4, "2026-11-15", 7, 45,
         json.dumps({"prefix": "logs/raw/2026-09", "compression": "zstd"}), "QUEUED",
         base_time + 260, "Routine monthly archival script")
    ]

    cursor.executemany("""
    INSERT INTO tasks (title, description, category, priority, due_date, insertion_sequence, estimated_duration, payload, status, created_at, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tasks)

    # Seed a few completed tasks for historical context
    completed_tasks = [
        ("SSL Certificate Rotation: *.priorityflow.io",
         "Production wildcard certificate automated renewal and deployment.",
         "Security Patch", 1, "2026-10-26", 8, 10,
         "{}", "COMPLETED", base_time - 1200, base_time - 1100, base_time - 1000,
         "Worker Node Alpha-01", "Certificates re-issued and propagated across CDNs"),

        ("Customer Data Export (GDPR Compliance)",
         "User account data retrieval and zip compilation for legal request.",
         "API Request", 2, "2026-10-26", 9, 15,
         "{}", "COMPLETED", base_time - 800, base_time - 700, base_time - 550,
         "Worker Node Beta-02", "Archived zip generated and dispatched via signed S3 link"),

        ("Redis Memory Defragmentation Sweep",
         "Maintenance defragmentation cycle on hot memory tier.",
         "Critical Infrastructure", 3, "2026-10-26", 10, 12,
         "{}", "COMPLETED", base_time - 600, base_time - 500, base_time - 380,
         "Worker Node Gamma-03", "Memory defragmentation cycle finished with 0 dropped keys")
    ]

    cursor.executemany("""
    INSERT INTO tasks (title, description, category, priority, due_date, insertion_sequence, estimated_duration, payload, status, created_at, started_at, completed_at, assigned_worker, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, completed_tasks)

    # Log seed event
    cursor.execute("""
    INSERT INTO heap_audit_logs (operation, task_id, details, timestamp)
    VALUES ('SEED_SAMPLES', NULL, 'Seeded 10 enterprise sample tasks into SQLite database.', ?)
    """, (time.time(),))

    conn.commit()
    conn.close()

    return get_all_tasks(db_path=db_path)


def clear_all_tasks(db_path: str = DB_FILE):
    """Empties all tasks and resets workers to test the empty state."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks")
    cursor.execute("UPDATE workers SET status = 'IDLE', current_task_id = NULL")
    cursor.execute("""
    INSERT INTO heap_audit_logs (operation, task_id, details, timestamp)
    VALUES ('CLEAR_ALL', NULL, 'Cleared all tasks from database to test empty state.', ?)
    """, (time.time(),))
    conn.commit()
    conn.close()


def create_task(title: str, priority: int, description: str = "",
                category: str = "General", due_date: str = "",
                estimated_duration: int = 12, payload: Dict[str, Any] = None,
                notes: str = "", db_path: str = DB_FILE) -> Dict[str, Any]:
    """
    Validates and adds a new task to SQLite.
    Automatically assigns:
    1. Unique Task ID (auto-increment primary key).
    2. Persistent monotonic insertion sequence number (COALESCE(MAX(insertion_sequence), 0) + 1).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    created_at = time.time()
    payload_str = json.dumps(payload or {})

    # Calculate persistent sequence number
    cursor.execute("SELECT COALESCE(MAX(insertion_sequence), 0) + 1 AS next_seq FROM tasks")
    insertion_sequence = cursor.fetchone()["next_seq"]

    cursor.execute("""
    INSERT INTO tasks (title, description, category, priority, due_date, insertion_sequence, estimated_duration, payload, status, created_at, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', ?, ?)
    """, (title, description, category, priority, due_date, insertion_sequence, estimated_duration, payload_str, created_at, notes))

    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": task_id,
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "due_date": due_date,
        "insertion_sequence": insertion_sequence,
        "estimated_duration": estimated_duration,
        "payload": payload or {},
        "status": "QUEUED",
        "created_at": created_at,
        "notes": notes
    }


def get_task(task_id: int, db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    res["payload"] = json.loads(res["payload"]) if res["payload"] else {}
    return res


def get_all_tasks(status: Optional[str] = None, category: Optional[str] = None,
                  search: Optional[str] = None, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if category and category != "ALL":
        query += " AND category = ?"
        params.append(category)

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR notes LIKE ? OR category LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for r in rows:
        t = dict(r)
        t["payload"] = json.loads(t["payload"]) if t["payload"] else {}
        tasks.append(t)
    return tasks


def get_queued_tasks(db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM tasks 
    WHERE status IN ('QUEUED', 'PENDING') 
    ORDER BY priority ASC, insertion_sequence ASC, created_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for r in rows:
        t = dict(r)
        t["payload"] = json.loads(t["payload"]) if t["payload"] else {}
        tasks.append(t)
    return tasks


def update_task_priority(task_id: int, new_priority: int, db_path: str = DB_FILE) -> bool:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET priority = ? WHERE id = ?", (new_priority, task_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def assign_task_to_worker(task_id: int, worker_name: str, algorithm_duration_ms: float = 0.0, db_path: str = DB_FILE) -> bool:
    """
    Atomically transitions a pending task to PROCESSING and assigns it to a worker.
    Safe synchronization strategy:
    Ensures that only eligible pending tasks ('QUEUED' or 'PENDING') can be claimed.
    If another concurrent request already claimed the task, rowcount will be 0 and
    returns False to strictly prevent double execution.
    Distinguishes the time spent executing the queue algorithm (algorithm_duration_ms)
    from the real-world duration of the task being worked on.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now = time.time()

    cursor.execute("""
    UPDATE tasks 
    SET status = 'PROCESSING', started_at = ?, assigned_worker = ?, algorithm_duration_ms = ?
    WHERE id = ? AND status IN ('QUEUED', 'PENDING')
    """, (now, worker_name, algorithm_duration_ms, task_id))

    if cursor.rowcount == 0:
        conn.close()
        return False

    cursor.execute("""
    UPDATE workers
    SET status = 'BUSY', current_task_id = ?
    WHERE name = ?
    """, (task_id, worker_name))

    conn.commit()
    conn.close()
    return True


def complete_task(task_id: int, db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    """
    Explicitly marks an active in-progress task as COMPLETED.
    Calculates the real-world execution duration (completed_at - started_at)
    and records the completion event in SQLite.
    Frees the assigned worker node back to IDLE.
    Ensures the completed task is strictly not eligible for execution again.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now = time.time()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    task = dict(row)
    started_at = task.get("started_at") or now
    real_world_duration_s = max(0.0, round(now - started_at, 2))
    worker_name = task.get("assigned_worker")

    cursor.execute("""
    UPDATE tasks
    SET status = 'COMPLETED', completed_at = ?, real_world_duration_s = ?
    WHERE id = ? AND status = 'PROCESSING'
    """, (now, real_world_duration_s, task_id))

    if cursor.rowcount == 0:
        conn.close()
        return None

    if worker_name:
        cursor.execute("""
        UPDATE workers
        SET status = 'IDLE', current_task_id = NULL, completed_count = completed_count + 1
        WHERE name = ?
        """, (worker_name,))

    cursor.execute("""
    INSERT INTO heap_audit_logs (operation, task_id, details, timestamp)
    VALUES ('COMPLETE', ?, ?, ?)
    """, (task_id, f"Completed task #{task_id} '{task['title']}'. Real-world execution duration: {real_world_duration_s}s.", now))

    conn.commit()
    conn.close()

    task["status"] = "COMPLETED"
    task["completed_at"] = now
    task["real_world_duration_s"] = real_world_duration_s
    return task


def cancel_task(task_id: int, db_path: str = DB_FILE) -> bool:
    """Cancels a task and marks status as CANCELLED."""
    return cancel_or_skip_task(task_id, reason="User cancelled task", db_path=db_path) is not None


def cancel_or_skip_task(task_id: int, reason: str = "User skipped task in Execution Simulator", db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    """
    Clearly defined status policy for canceling/skipping a task:
    1. If the task is In Progress (PROCESSING), releases the assigned worker node back to IDLE.
    2. Updates status permanently to 'CANCELLED' in SQLite with cancellation timestamp and reason.
    3. Records the cancellation event in heap_audit_logs.
    4. Ensures the task is strictly not eligible for execution again.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now = time.time()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    task = dict(row)
    worker_name = task.get("assigned_worker")

    cursor.execute("""
    UPDATE tasks
    SET status = 'CANCELLED', completed_at = ?, notes = ?
    WHERE id = ? AND status IN ('QUEUED', 'PENDING', 'PROCESSING')
    """, (now, f"Cancelled/Skipped: {reason}", task_id))

    if cursor.rowcount == 0:
        conn.close()
        return None

    if worker_name:
        cursor.execute("""
        UPDATE workers
        SET status = 'IDLE', current_task_id = NULL
        WHERE name = ?
        """, (worker_name,))

    cursor.execute("""
    INSERT INTO heap_audit_logs (operation, task_id, details, timestamp)
    VALUES ('CANCEL', ?, ?, ?)
    """, (task_id, f"Task #{task_id} '{task['title']}' cancelled/skipped. {reason}", now))

    conn.commit()
    conn.close()

    task["status"] = "CANCELLED"
    return task


def get_active_in_progress_task(db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    """Returns the currently active In-Progress (PROCESSING) task, if one exists."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM tasks 
    WHERE status = 'PROCESSING'
    ORDER BY started_at DESC
    LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    res["payload"] = json.loads(res["payload"]) if res.get("payload") else {}
    return res


def get_workers(db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT w.id, w.name, w.region, w.status, w.completed_count, w.current_task_id,
           t.title as current_task_title, t.priority as current_task_priority,
           t.category as current_task_category, t.started_at as current_task_started_at
    FROM workers w
    LEFT JOIN tasks t ON w.current_task_id = t.id
    ORDER BY w.id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_idle_worker(db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE status = 'IDLE' ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def log_heap_audit(operation: str, task_id: Optional[int], details: str, db_path: str = DB_FILE):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO heap_audit_logs (operation, task_id, details, timestamp)
    VALUES (?, ?, ?, ?)
    """, (operation, task_id, details, time.time()))
    conn.commit()
    conn.close()


def get_recent_audit_logs(limit: int = 20, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM heap_audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overview_statistics(db_path: str = DB_FILE) -> Dict[str, Any]:
    """
    Computes overview metrics directly from SQLite:
    - Total tasks
    - Pending tasks (QUEUED)
    - In-progress tasks (PROCESSING)
    - Completed tasks
    - Critical-priority tasks (Priority 1)
    - Current queue size
    - Total insert operations
    - Total extraction operations
    - Priority distribution (1 to 4)
    - Status distribution (Pending, In-Progress, Completed, Cancelled)
    - Recent execution events
    - Empty state check
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Total tasks
    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    total_tasks = cursor.fetchone()["count"]

    # 2. Status counts
    cursor.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
    status_map = {r["status"]: r["count"] for r in cursor.fetchall()}
    pending_tasks = status_map.get("QUEUED", 0)
    in_progress_tasks = status_map.get("PROCESSING", 0)
    completed_tasks = status_map.get("COMPLETED", 0)
    cancelled_tasks = status_map.get("CANCELLED", 0)

    # 3. Critical-priority tasks (Priority 1)
    cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE priority = 1 AND status != 'CANCELLED'")
    critical_priority_tasks = cursor.fetchone()["count"]

    # 4. Total insert operations in audit logs
    cursor.execute("""
    SELECT COUNT(*) as count FROM heap_audit_logs 
    WHERE operation IN ('INSERT', 'BURST_INJECTION', 'SEED_SAMPLES')
    """)
    total_inserts = cursor.fetchone()["count"]

    # 5. Total extraction operations in audit logs
    cursor.execute("""
    SELECT COUNT(*) as count FROM heap_audit_logs 
    WHERE operation IN ('EXTRACT_MIN', 'AUTO_DISPATCH')
    """)
    total_extractions = cursor.fetchone()["count"]

    # 6. Priority distribution across all non-cancelled tasks
    cursor.execute("SELECT priority, COUNT(*) as count FROM tasks WHERE status != 'CANCELLED' GROUP BY priority")
    priority_distribution = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in cursor.fetchall():
        prio = r["priority"]
        if prio in priority_distribution:
            priority_distribution[prio] = r["count"]

    # 7. Recent execution events from audit logs
    cursor.execute("SELECT * FROM heap_audit_logs ORDER BY timestamp DESC LIMIT 10")
    recent_events = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "in_progress_tasks": in_progress_tasks,
        "completed_tasks": completed_tasks,
        "cancelled_tasks": cancelled_tasks,
        "critical_priority_tasks": critical_priority_tasks,
        "current_queue_size": pending_tasks,
        "total_inserts": total_inserts,
        "total_extractions": total_extractions,
        "priority_distribution": priority_distribution,
        "status_distribution": {
            "Pending": pending_tasks,
            "In-Progress": in_progress_tasks,
            "Completed": completed_tasks,
            "Cancelled": cancelled_tasks
        },
        "recent_events": recent_events,
        "is_empty": total_tasks == 0
    }


def get_performance_analytics(db_path: str = DB_FILE) -> Dict[str, Any]:
    """Computes SaaS performance metrics for Chart.js display."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
    status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("""
    SELECT priority, COUNT(*) as count 
    FROM tasks 
    WHERE status = 'QUEUED' 
    GROUP BY priority
    """)
    priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in cursor.fetchall():
        prio = r["priority"]
        if prio in priority_counts:
            priority_counts[prio] = r["count"]

    cursor.execute("""
    SELECT priority, AVG(started_at - created_at) as avg_latency_sec
    FROM tasks
    WHERE started_at IS NOT NULL
    GROUP BY priority
    """)
    latency_by_priority = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    for r in cursor.fetchall():
        prio = r["priority"]
        if prio in latency_by_priority:
            latency_by_priority[prio] = round(r["avg_latency_sec"] or 0.0, 1)

    cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'COMPLETED'")
    total_completed = cursor.fetchone()["count"]

    cursor.execute("SELECT status, COUNT(*) as count FROM workers GROUP BY status")
    worker_status = {r["status"]: r["count"] for r in cursor.fetchall()}

    conn.close()

    return {
        "status_counts": {
            "queued": status_counts.get("QUEUED", 0),
            "processing": status_counts.get("PROCESSING", 0),
            "completed": status_counts.get("COMPLETED", 0),
            "cancelled": status_counts.get("CANCELLED", 0)
        },
        "priority_distribution": priority_counts,
        "avg_latency_by_priority": latency_by_priority,
        "total_completed": total_completed,
        "worker_utilization": worker_status
    }
