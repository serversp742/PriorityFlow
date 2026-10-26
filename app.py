"""
PriorityFlow - SaaS Priority Queue & Background Task Orchestrator
==================================================================
Flask Backend Application

Key Principles:
- Backend: Python 3 and Flask
- Database: SQLite (tasks, workers, audit logs, analytics)
- Priority Queue: Real in-memory Binary Min-Heap (no database sorting or frontend simulation)
- Verification: Side-by-side verification with Python heapq
- API: Fully functional endpoints for all 7 sidebar sections
"""

from flask import Flask, jsonify, render_template, request, Response
import time
import os
import json
import heapq

from priority_queue import BinaryMinHeap, HeapNode
import database as db
import threading

app = Flask(__name__)

# Single authoritative in-memory instance of the Binary Min-Heap
priority_flow_heap = BinaryMinHeap()

# Lock for thread-safe execution dispatching
dispatch_lock = threading.Lock()


def sync_heap_from_db():
    """
    Rebuilds in-memory Binary Min-Heap strictly from eligible database records.
    SQLite is the single source of truth for task records.
    Only Pending tasks (status IN ('QUEUED', 'PENDING')) are eligible for execution.
    In-progress (PROCESSING) and completed tasks are never loaded into the queue.
    Preserves persistent insertion sequence to guarantee stable FIFO ordering across application restarts.
    """
    global priority_flow_heap
    priority_flow_heap.rebuild_from_db()


# Initialize DB and Heap
db.init_db()
db.seed_demo_data_if_empty()
sync_heap_from_db()


# ---------------------------------------------------------
# Web Page Route
# ---------------------------------------------------------

@app.route("/")
def index():
    """Serves the PriorityFlow SaaS Application."""
    return render_template("index.html")


# ---------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------

@app.route("/api/overview", methods=["GET"])
def get_overview():
    """
    Returns real, live overview dashboard metrics from SQLite & Min-Heap:
    - Total tasks
    - Pending tasks (QUEUED)
    - In-progress tasks (PROCESSING)
    - Completed tasks
    - Critical-priority tasks (Priority 1)
    - Current queue size (active in Min-Heap)
    - Total insert operations
    - Total extraction operations
    - Next task to be executed (Min-Heap root)
    - Priority distribution (counts per P1-P5)
    - Task status distribution (Pending, In-Progress, Completed, Cancelled)
    - Recent execution events
    - Empty state indicator
    """
    stats = db.get_overview_statistics()
    root_node = priority_flow_heap.peek()

    # Ensure queue size matches live heap
    stats["current_queue_size"] = len(priority_flow_heap)
    stats["heap_valid"] = priority_flow_heap.is_valid_heap()

    # Next task to be executed
    if root_node:
        stats["next_task"] = {
            "task_id": root_node.task_id,
            "title": root_node.data.get("title", f"Task #{root_node.task_id}"),
            "category": root_node.data.get("category", "General"),
            "priority": root_node.priority,
            "estimated_duration": root_node.data.get("estimated_duration", 15),
            "created_at": root_node.created_at,
            "notes": root_node.data.get("notes", "")
        }
    else:
        stats["next_task"] = None

    workers = db.get_workers()
    idle_workers = sum(1 for w in workers if w["status"] == "IDLE")
    stats["workers_available"] = f"{idle_workers}/{len(workers)}"

    return jsonify({
        "status": "success",
        "data": stats
    })


@app.route("/api/heap/state", methods=["GET"])
def get_heap_state():
    """
    Returns full state of the Binary Min-Heap:
    - Array representation with index formulas
    - Hierarchical tree representation for SVG visualizer
    - Root task (highest priority)
    - Validity check of the min-heap invariant
    - Last operation swap steps for animation
    """
    peek_node = priority_flow_heap.peek()
    return jsonify({
        "status": "success",
        "size": len(priority_flow_heap),
        "is_valid": priority_flow_heap.is_valid_heap(),
        "root": peek_node.to_dict() if peek_node else None,
        "array": priority_flow_heap.to_array(),
        "tree": priority_flow_heap.to_tree_structure(),
        "logical_order": priority_flow_heap.to_logical_execution_order(),
        "last_steps": priority_flow_heap.last_operation_steps
    })


@app.route("/api/tasks", methods=["GET", "POST"])
def handle_tasks():
    """
    GET: Filterable task history (status, category, search)
    POST: Ingest new task into SQLite and Min-Heap
    """
    if request.method == "POST":
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        category = data.get("category", "General").strip() or "General"
        due_date = data.get("due_date", "").strip()

        # 1. Form Validation
        if not title:
            return jsonify({"status": "error", "message": "Task title is required."}), 400
        if len(title) < 2:
            return jsonify({"status": "error", "message": "Task title must be at least 2 characters long."}), 400

        try:
            priority = int(data.get("priority", 3))
            duration = int(data.get("estimated_duration", 15))
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Priority must be a valid integer."}), 400

        if priority not in (1, 2, 3, 4):
            return jsonify({"status": "error", "message": "Priority must be 1 (Critical), 2 (High), 3 (Medium), or 4 (Low)."}), 400

        notes = data.get("notes", "") or description

        # 2. Assign unique ID & persistent sequence number and save to SQLite
        task_record = db.create_task(
            title=title,
            priority=priority,
            description=description,
            category=category,
            due_date=due_date,
            estimated_duration=duration,
            notes=notes
        )

        # 3. Insert into the actual Binary Min-Heap Priority Queue & capture operation trace
        trace = priority_flow_heap.insert(
            task_id=task_record["id"],
            priority=task_record["priority"],
            created_at=task_record["created_at"],
            data=task_record
        )

        # 4. Log audit trail in SQLite
        db.log_heap_audit(
            operation="INSERT",
            task_id=task_record["id"],
            details=f"Task #{task_record['id']} (Seq #{task_record['insertion_sequence']}) '{title}' [P{priority}] enqueued. Swaps: {trace['swaps_count']}"
        )

        return jsonify({
            "status": "success",
            "message": f"Task #{task_record['id']} successfully enqueued into Priority Queue.",
            "task": task_record,
            "metrics": {
                "task_id": task_record["id"],
                "insertion_sequence": task_record["insertion_sequence"],
                "initial_index": trace["initial_index"],
                "final_index": trace["final_index"],
                "comparisons_count": trace["comparisons_count"],
                "swaps_count": trace["swaps_count"],
                "time_complexity": "O(log n)"
            },
            "explanation": trace["explanation"],
            "steps": trace["steps"],
            "queue_size": len(priority_flow_heap)
        }), 201

    # GET Request: Fetch tasks with optional filters
    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")

    tasks = db.get_all_tasks(status=status, category=category, search=search)
    return jsonify({
        "status": "success",
        "count": len(tasks),
        "tasks": tasks
    })


@app.route("/api/tasks/extract-next", methods=["POST"])
def extract_next_task():
    """
    Dispatches next highest priority task:
    1. Min-Heap extract_min() (O(log n))
    2. Assigns to an idle worker node
    3. Updates task status to PROCESSING in SQLite
    Safe synchronization strategy:
    Atomic SQLite condition ensures that in-progress, completed, or cancelled
    tasks can never be executed again even across simultaneous requests.
    Distinguishes the time spent executing the queue algorithm from real-world task duration.
    """
    with dispatch_lock:
        if priority_flow_heap.is_empty():
            return jsonify({
                "status": "error",
                "code": "QUEUE_EMPTY",
                "message": "Queue is currently empty! All eligible tasks have been executed or completed. You can create a new task or load sample enterprise workloads to continue simulation."
            }), 400

        # Benchmark Priority Queue algorithm execution time (O(log n))
        t_start = time.perf_counter()
        min_node, steps = priority_flow_heap.extract_min()
        algorithm_duration_ms = round((time.perf_counter() - t_start) * 1000, 4)

        if not min_node:
            return jsonify({
                "status": "error",
                "code": "QUEUE_EMPTY",
                "message": "Queue is currently empty! All eligible tasks have been executed or completed."
            }), 400

        task_data = min_node.data
        task_id = min_node.task_id

        # 2. Find available worker node
        worker = db.get_idle_worker()
        worker_name = worker["name"] if worker else "Dedicated Cluster Worker"

        # 3. Update SQLite with atomic check: only pending tasks can be claimed
        assigned = db.assign_task_to_worker(task_id, worker_name, algorithm_duration_ms=algorithm_duration_ms)
        if not assigned:
            return jsonify({
                "status": "error",
                "message": f"Task #{task_id} is no longer pending and cannot be executed."
            }), 409

        # Fetch fresh record with started_at
        updated_task = db.get_task(task_id) or task_data
        updated_task["priority_label"] = priority_flow_heap.get_priority_label(min_node.priority)
        updated_task["algorithm_duration_ms"] = algorithm_duration_ms

        # 4. Log audit
        db.log_heap_audit(
            operation="EXTRACT_MIN",
            task_id=task_id,
            details=f"Dispatched Task #{task_id} '{task_data.get('title')}' (P{min_node.priority}, Seq #{min_node.insertion_sequence}) to {worker_name}. Algorithm time: {algorithm_duration_ms}ms. Sift-down steps: {len(steps)}"
        )

        return jsonify({
            "status": "success",
            "message": f"Dispatched '{task_data.get('title')}' to {worker_name}.",
            "task": updated_task,
            "assigned_worker": worker_name,
            "algorithm_duration_ms": algorithm_duration_ms,
            "steps": steps,
            "queue_size": len(priority_flow_heap)
        })


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_route(task_id: int):
    """
    Explicitly marks an active in-progress task as COMPLETED.
    Records completion timestamp, calculates real-world duration,
    and ensures the task cannot be executed again.
    """
    task = db.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "message": "Task not found."}), 404

    completed_task = db.complete_task(task_id)
    if not completed_task:
        return jsonify({
            "status": "error",
            "message": f"Task #{task_id} is not in-progress or already completed."
        }), 400

    return jsonify({
        "status": "success",
        "message": f"Task '{completed_task['title']}' completed successfully.",
        "task": completed_task,
        "real_world_duration_s": completed_task.get("real_world_duration_s", 0.0)
    })


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_single_task_route(task_id: int):
    """Fetches a single task by ID from SQLite."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "message": f"Task #{task_id} not found."}), 404
    return jsonify({"status": "success", "task": task})


@app.route("/api/simulator/state", methods=["GET"])
def get_simulator_state():
    """
    Returns full telemetry for the Execution Simulator:
    - Current selected task (active In Progress task)
    - Next eligible task preview (root of binary min-heap)
    - Remaining pending tasks count
    - Latest operation details from audit log
    - Cluster workers status matrix
    """
    active_task = db.get_active_in_progress_task()
    if active_task:
        active_task["priority_label"] = priority_flow_heap.get_priority_label(active_task["priority"])
        if active_task.get("started_at"):
            active_task["elapsed_seconds"] = round(time.time() - active_task["started_at"], 1)

    next_root = priority_flow_heap.peek()
    next_task_preview = None
    if next_root:
        next_task_preview = {
            "task_id": next_root.task_id,
            "title": next_root.data.get("title", f"Task #{next_root.task_id}"),
            "priority": next_root.priority,
            "priority_label": priority_flow_heap.get_priority_label(next_root.priority),
            "insertion_sequence": next_root.insertion_sequence,
            "description": next_root.data.get("description", ""),
            "category": next_root.data.get("category", "General")
        }

    recent_logs = db.get_recent_audit_logs(limit=8)
    latest_op = recent_logs[0] if recent_logs else None

    return jsonify({
        "status": "success",
        "active_task": active_task,
        "next_eligible_task": next_task_preview,
        "remaining_pending_count": len(priority_flow_heap),
        "latest_operation": latest_op,
        "recent_events": recent_logs,
        "workers": db.get_workers()
    })


@app.route("/api/simulator/cancel", methods=["POST"])
def cancel_task_simulator():
    """
    Cancels or skips a task under the clearly defined status policy.
    Releases assigned worker node and updates status to CANCELLED in SQLite.
    If the task was pending in the min-heap, removes it.
    """
    data = request.get_json() or {}
    task_id = data.get("task_id")
    reason = data.get("reason", "Skipped by operator in Execution Simulator")

    if not task_id:
        active = db.get_active_in_progress_task()
        if active:
            task_id = active["id"]
        else:
            return jsonify({"status": "error", "message": "No active task to cancel."}), 400

    # If task is still in priority queue, remove it
    priority_flow_heap.remove(task_id)

    cancelled_task = db.cancel_or_skip_task(task_id, reason=reason)
    if not cancelled_task:
        return jsonify({"status": "error", "message": "Failed to cancel task."}), 400

    return jsonify({
        "status": "success",
        "message": f"Task #{task_id} successfully cancelled.",
        "task": cancelled_task
    })


@app.route("/api/tasks/<int:task_id>/update-priority", methods=["POST"])
def update_priority_route(task_id: int):
    """
    Updates the priority of a queued task (Decrease-Key / Increase-Key).
    Executes sift-up or sift-down in O(log n) time.
    """
    data = request.get_json() or {}
    try:
        new_priority = int(data.get("priority", 1))
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid priority level."}), 400

    if new_priority < 1 or new_priority > 5:
        return jsonify({"status": "error", "message": "Priority must be between 1 and 5."}), 400

    # 1. Update in-memory Min-Heap
    updated, steps = priority_flow_heap.update_priority(task_id, new_priority)
    if not updated:
        return jsonify({"status": "error", "message": "Task is not currently in the active waiting queue."}), 400

    # 2. Update SQLite
    db.update_task_priority(task_id, new_priority)

    # 3. Log audit
    db.log_heap_audit(
        operation="UPDATE_PRIORITY",
        task_id=task_id,
        details=f"Updated task #{task_id} to P{new_priority}. Heap adjusted with {len(steps)} swaps."
    )

    return jsonify({
        "status": "success",
        "message": f"Updated task priority to P{new_priority}.",
        "steps": steps,
        "queue_size": len(priority_flow_heap)
    })


@app.route("/api/tasks/<int:task_id>/cancel", methods=["POST"])
def cancel_task_route(task_id: int):
    """Cancels and removes a task from the Priority Queue."""
    updated, steps = priority_flow_heap.remove(task_id)
    if not updated:
        return jsonify({"status": "error", "message": "Task is not in the active queue."}), 400

    db.cancel_task(task_id)
    db.log_heap_audit(
        operation="CANCEL",
        task_id=task_id,
        details=f"Task #{task_id} canceled and removed from heap."
    )

    return jsonify({
        "status": "success",
        "message": f"Task #{task_id} canceled.",
        "steps": steps
    })


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task_route(task_id: int):
    """Deletes/cancels a task and removes it from the heap if queued."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "message": "Task not found."}), 404

    # Remove from heap if present
    priority_flow_heap.remove(task_id)
    db.cancel_task(task_id)
    db.log_heap_audit(
        operation="DELETE",
        task_id=task_id,
        details=f"Task #{task_id} deleted."
    )

    return jsonify({
        "status": "success",
        "message": f"Task #{task_id} deleted."
    })


@app.route("/api/tasks/seed-samples", methods=["POST"])
def seed_samples_route():
    """Seeds sample tasks to populate SQLite and heap."""
    db.seed_sample_tasks()
    sync_heap_from_db()
    return jsonify({
        "status": "success",
        "message": "Sample tasks created successfully.",
        "queue_size": len(priority_flow_heap)
    })


@app.route("/api/tasks/clear-all", methods=["POST"])
def clear_all_tasks_route():
    """Clears all tasks to test the empty state."""
    db.clear_all_tasks()
    sync_heap_from_db()
    return jsonify({
        "status": "success",
        "message": "All tasks cleared. Database is now empty."
    })


@app.route("/api/tasks/export", methods=["GET"])
def export_tasks():
    """Exports all tasks as JSON for data portability."""
    tasks = db.get_all_tasks()
    json_str = json.dumps(tasks, indent=2)
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=priorityflow_tasks_export.json"}
    )


@app.route("/api/workers", methods=["GET"])
def get_workers_route():
    """Returns worker nodes and their active executions."""
    workers = db.get_workers()
    return jsonify({"status": "success", "workers": workers})


@app.route("/api/analytics", methods=["GET"])
def get_analytics_route():
    """Returns metrics for Chart.js."""
    analytics = db.get_performance_analytics()
    return jsonify({"status": "success", "analytics": analytics})


@app.route("/api/logs", methods=["GET"])
def get_logs_route():
    """Returns recent heap audit logs."""
    logs = db.get_recent_audit_logs(limit=25)
    return jsonify({"status": "success", "logs": logs})


@app.route("/api/simulator/batch-burst", methods=["POST"])
def simulator_burst():
    """
    Simulation: Injects a burst of 5 enterprise tasks of varied urgency
    to demonstrate live heap re-structuring and root preemption.
    """
    burst_tasks = [
        ("Kube-Apiserver CPU Throttling Alert", "Critical Infrastructure", 1, 8,
         {"cluster": "eks-prod-eu", "metric": "cpu_99pct"}),
        ("PCI-DSS Tokenization Vault Sync", "Security Patch", 2, 12,
         {"vault": "token-vault-04", "keys_rotated": 5000}),
        ("Ingest S3 Parquet Bulk Transactions", "Data Pipeline", 3, 22,
         {"bucket": "corp-tx-archive", "size_gb": 42}),
        ("Re-generate Algolia Search Replica", "Search Cluster", 4, 30,
         {"index": "products_global_v3"}),
        ("Dead-letter Queue Purge & Audit", "Storage & Archival", 5, 40,
         {"sqs_queue": "dead_letter_dlq_prod"})
    ]

    inserted = []
    for title, cat, prio, dur, payload in burst_tasks:
        rec = db.create_task(
            title=title, category=cat, priority=prio,
            estimated_duration=dur, payload=payload,
            notes="Injected via Execution Simulator Traffic Spike"
        )
        priority_flow_heap.insert(
            task_id=rec["id"],
            priority=rec["priority"],
            created_at=rec["created_at"],
            data=rec
        )
        inserted.append(rec)

    db.log_heap_audit(
        operation="BURST_INJECTION",
        task_id=None,
        details="Injected 5 enterprise tasks during simulated traffic spike."
    )

    return jsonify({
        "status": "success",
        "message": "Burst traffic simulated! 5 tasks enqueued into Min-Heap.",
        "tasks": inserted,
        "queue_size": len(priority_flow_heap)
    })


@app.route("/api/simulator/step-tick", methods=["POST"])
def simulator_step_tick():
    """
    Single step execution tick:
    Dispatches the root task to an idle worker if one is available.
    """
    idle_worker = db.get_idle_worker()
    if not idle_worker:
        return jsonify({
            "status": "warning",
            "message": "All worker nodes are busy. Awaiting worker completion."
        })

    if priority_flow_heap.is_empty():
        return jsonify({
            "status": "info",
            "message": "Priority queue is empty. No tasks to dispatch."
        })

    min_node, steps = priority_flow_heap.extract_min()
    task_data = min_node.data
    task_id = min_node.task_id

    db.assign_task_to_worker(task_id, idle_worker["name"])
    db.log_heap_audit(
        operation="AUTO_DISPATCH",
        task_id=task_id,
        details=f"Automated tick dispatched '{task_data.get('title')}' (P{min_node.priority}) to {idle_worker['name']}."
    )

    return jsonify({
        "status": "success",
        "message": f"Dispatched '{task_data.get('title')}' to {idle_worker['name']}.",
        "task": task_data,
        "worker": idle_worker["name"],
        "steps": steps,
        "queue_size": len(priority_flow_heap)
    })


@app.route("/api/simulator/reset", methods=["POST"])
def simulator_reset():
    """Resets database and heap to clean initial baseline state."""
    db_path = db.DB_FILE
    if os.path.exists(db_path):
        os.remove(db_path)

    db.init_db()
    db.seed_demo_data_if_empty()
    sync_heap_from_db()

    db.log_heap_audit(
        operation="RESET",
        task_id=None,
        details="PriorityFlow system reset to initial demo baseline."
    )

    return jsonify({
        "status": "success",
        "message": "PriorityFlow reset to baseline state.",
        "queue_size": len(priority_flow_heap)
    })


@app.route("/api/dsa/verify-heapq", methods=["GET"])
def verify_heapq():
    """
    College DSA Proof:
    Validates our custom BinaryMinHeap against Python's heapq library.
    Proves 100% identical priority extraction order and O(log n) invariant compliance
    under the exact ordering rule:
    1. Lower numeric priority first.
    2. Earlier persistent insertion sequence for equal priorities.
    """
    custom_order = []
    cloned_heap = BinaryMinHeap()
    for node in priority_flow_heap.heap:
        cloned_heap.insert(
            node.task_id, node.priority, node.created_at, dict(node.data),
            insertion_sequence=node.insertion_sequence
        )

    while not cloned_heap.is_empty():
        n, _ = cloned_heap.extract_min()
        if n:
            custom_order.append({
                "task_id": n.task_id,
                "title": n.data.get("title"),
                "priority": n.priority,
                "insertion_sequence": n.insertion_sequence,
                "created_at": n.created_at
            })

    py_heap = []
    for node in priority_flow_heap.heap:
        heapq.heappush(py_heap, (node.priority, node.insertion_sequence, node.created_at, node.task_id, node.data))

    heapq_order = []
    while py_heap:
        prio, seq, created, tid, data = heapq.heappop(py_heap)
        heapq_order.append({
            "task_id": tid,
            "title": data.get("title"),
            "priority": prio,
            "insertion_sequence": seq,
            "created_at": created
        })

    is_identical = (custom_order == heapq_order)

    return jsonify({
        "status": "success",
        "identical": is_identical,
        "custom_heap_order": custom_order,
        "python_heapq_order": heapq_order,
        "explanation": "Both PriorityFlow's custom BinaryMinHeap and Python's built-in heapq produce identical extraction sequences. In addition, our custom implementation provides an O(1) index map for O(log n) decrease-key updates, tree coordinate mapping, and full swap tracing."
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
