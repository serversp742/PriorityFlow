"""
PriorityFlow - Binary Min-Heap Priority Queue Engine
=====================================================
Custom, high-performance Binary Min-Heap implementation for task orchestration.

Priority Tiers (Emergency / SLA Severity):
- 1 = Critical — highest priority (Immediate SLA execution)
- 2 = High (Urgent operational priority)
- 3 = Medium (Standard scheduled priority)
- 4 = Low — lowest priority (Deferrable background workload)

Lower numbers represent higher scheduling priority:
- Root (index 0) is ALWAYS the task with highest urgency.
- Tie-breaking: If two tasks have the same priority level, earlier creation timestamp
  takes precedence (Strict FIFO ordering within the same tier).

Time Complexities:
- Peek Highest Urgency Task:      O(1)
- Insert (Enqueue Task):           O(log n)
- Extract-Min (Dispatch Task):     O(log n)
- Update Priority (Decrease/Key):  O(log n) with O(1) index map
- Heap Invariant Verification:     O(n)
- Contiguous Array Memory:         O(n) space

Indexing Formulas for Array Representation:
- Parent(i)      = floor((i - 1) / 2)
- Left Child(i)  = 2 * i + 1
- Right Child(i) = 2 * i + 2
"""

from typing import Any, Dict, List, Optional, Tuple
import time
import threading


class InsertionTrace(dict):
    """
    Rich insertion trace dictionary containing exact comparisons, swaps,
    initial/final indices, and a human-readable explanation generated
    directly from the real algorithm trace.
    """
    def __init__(self, steps: List[Dict[str, Any]], initial_index: int, final_index: int,
                 comparisons_count: int, swaps_count: int, explanation: str,
                 comparisons: List[Dict[str, Any]], swaps: List[Dict[str, Any]]):
        super().__init__({
            "steps": steps,
            "initial_index": initial_index,
            "final_index": final_index,
            "comparisons_count": comparisons_count,
            "swaps_count": swaps_count,
            "explanation": explanation,
            "comparisons": comparisons,
            "swaps": swaps
        })
        self.steps = steps
        self.initial_index = initial_index
        self.final_index = final_index
        self.comparisons_count = comparisons_count
        self.swaps_count = swaps_count
        self.explanation = explanation

    def __iter__(self):
        return iter(self.steps)

    def __len__(self):
        return len(self.steps)


class HeapNode:
    """
    Represents a single task node inside the Binary Min-Heap.

    Ordering Rule:
    1. First: lower numeric priority (1 = Critical is prioritized before 2 = High).
    2. Second: earlier persistent insertion sequence for equal priorities (FIFO stability across restarts).
    3. Third: created_at timestamp tie-breaker.
    4. Fourth: unique task_id.
    """

    def __init__(self, task_id: int, priority: int, created_at: float, data: Dict[str, Any], insertion_sequence: int = 0):
        self.task_id = int(task_id)
        self.priority = int(priority)
        self.created_at = float(created_at)
        self.data = dict(data or {})
        self.insertion_sequence = int(insertion_sequence or self.data.get("insertion_sequence", 0))
        if "insertion_sequence" not in self.data:
            self.data["insertion_sequence"] = self.insertion_sequence

    @property
    def key(self) -> Tuple[int, int, float, int]:
        """
        Comparison key tuple enforcing the exact priority rules:
        First: lower numeric priority.
        Second: earlier persistent insertion sequence for equal priorities.
        """
        return (self.priority, self.insertion_sequence, self.created_at, self.task_id)

    def __lt__(self, other: "HeapNode") -> bool:
        return self.key < other.key

    def __le__(self, other: "HeapNode") -> bool:
        return self.key <= other.key

    def __gt__(self, other: "HeapNode") -> bool:
        return self.key > other.key

    def __ge__(self, other: "HeapNode") -> bool:
        return self.key >= other.key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HeapNode):
            return False
        return self.task_id == other.task_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "priority": self.priority,
            "insertion_sequence": self.insertion_sequence,
            "created_at": self.created_at,
            "data": self.data
        }


class BinaryMinHeap:
    """
    Authoritative In-Memory Binary Min-Heap for PriorityFlow.

    Pedagogical Note on Ordering:
    -----------------------------
    A Binary Min-Heap does NOT store every element in fully sorted order!
    The heap is a semi-ordered complete binary tree satisfying the min-heap
    invariant: A[floor((i-1)/2)] <= A[i] for every child node i > 0.
    The heap guarantees ONLY that its root element (index 0) is the highest-priority
    eligible element under the chosen ordering rule (lower numeric priority first,
    then earlier persistent insertion sequence for tie-breaking).

    Features:
    - Thread-safe operations using threading.RLock
    - Real O(1) index lookup map (self.index_map)
    - Full trace logging of comparisons and swaps
    - O(n) linear-time Floyd's heap construction (build_heap)
    - SQLite queue rebuilding from eligible pending tasks
    """

    def __init__(self):
        self.heap: List[HeapNode] = []
        self.index_map: Dict[int, int] = {}
        self.last_operation_steps: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def __len__(self) -> int:
        with self._lock:
            return len(self.heap)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self.heap) == 0

    @staticmethod
    def parent_index(i: int) -> int:
        return (i - 1) // 2

    @staticmethod
    def left_child_index(i: int) -> int:
        return 2 * i + 1

    @staticmethod
    def right_child_index(i: int) -> int:
        return 2 * i + 2

    def peek(self) -> Optional[HeapNode]:
        """Returns the highest priority task at the root without removing it. O(1)."""
        with self._lock:
            if self.is_empty():
                return None
            return self.heap[0]

    def sift_up(self, index: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Public interface for Sift-Up operation."""
        with self._lock:
            return self._sift_up(index)

    def sift_down(self, index: int) -> None:
        """Public interface for Sift-Down operation."""
        with self._lock:
            self._sift_down(index)

    def build_heap(self, nodes: List[HeapNode]) -> None:
        """
        Floyd's algorithm for linear-time heap construction: O(n).
        Rearranges an arbitrary list of HeapNode objects into a valid min-heap
        by sifting down each non-leaf node starting from floor(n/2) - 1 down to root 0.
        Guarantees min-heap invariant holds across all nodes.
        """
        with self._lock:
            self.heap = list(nodes)
            self.index_map = {node.task_id: i for i, node in enumerate(self.heap)}
            self.last_operation_steps = []
            n = len(self.heap)
            for i in range(n // 2 - 1, -1, -1):
                self._sift_down(i)

    def rebuild_from_db(self, db_path: Optional[str] = None) -> int:
        """
        Rebuilds the in-memory Binary Min-Heap strictly from eligible pending tasks in SQLite.
        Only Pending tasks (status IN ('QUEUED', 'PENDING')) are eligible for execution.
        In-progress (PROCESSING), completed (COMPLETED), and cancelled/deleted tasks are strictly excluded.
        Preserves persistent insertion sequence to ensure stable FIFO ordering across application restarts.
        Time Complexity: O(n) Floyd's heap construction.
        """
        with self._lock:
            import database as db
            target_db = db_path or db.DB_FILE
            queued_tasks = db.get_queued_tasks(db_path=target_db)

            nodes = []
            for t in queued_tasks:
                status = str(t.get("status", "QUEUED")).upper()
                if status not in ("QUEUED", "PENDING"):
                    continue
                nodes.append(HeapNode(
                    task_id=t["id"],
                    priority=t["priority"],
                    created_at=t["created_at"],
                    data=t,
                    insertion_sequence=t.get("insertion_sequence", 0)
                ))

            self.build_heap(nodes)
            return len(self.heap)

    def clear(self) -> None:
        """Clears all tasks from the in-memory queue."""
        with self._lock:
            self.heap.clear()
            self.index_map.clear()
            self.last_operation_steps.clear()

    def _swap(self, i: int, j: int, reason: str = "swap"):
        """Swaps elements at index i and j and updates position tracking map."""
        node_i = self.heap[i]
        node_j = self.heap[j]

        step_record = {
            "action": "swap",
            "index_a": i,
            "task_a": node_i.data.get("title", f"Task #{node_i.task_id}"),
            "priority_a": node_i.priority,
            "index_b": j,
            "task_b": node_j.data.get("title", f"Task #{node_j.task_id}"),
            "priority_b": node_j.priority,
            "reason": reason
        }
        self.last_operation_steps.append(step_record)

        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]
        self.index_map[self.heap[i].task_id] = i
        self.index_map[self.heap[j].task_id] = j
        return step_record

    def _sift_up(self, index: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Restores min-heap property upward: parent.key <= child.key.
        Comparison uses HeapNode.key: (priority, insertion_sequence, created_at, task_id).
        Time Complexity: O(log n)
        Returns: (comparisons, swaps)
        """
        comparisons = []
        swaps = []

        while index > 0:
            parent_idx = self.parent_index(index)
            parent_node = self.heap[parent_idx]
            child_node = self.heap[index]

            is_child_higher_priority = child_node < parent_node

            comparison_event = {
                "action": "compare",
                "child_index": index,
                "child_task": child_node.data.get("title", f"Task #{child_node.task_id}"),
                "child_priority": child_node.priority,
                "parent_index": parent_idx,
                "parent_task": parent_node.data.get("title", f"Task #{parent_node.task_id}"),
                "parent_priority": parent_node.priority,
                "swap_needed": is_child_higher_priority
            }
            comparisons.append(comparison_event)
            self.last_operation_steps.append(comparison_event)

            if is_child_higher_priority:
                swap_event = self._swap(
                    index, parent_idx,
                    reason=f"Child (P{child_node.priority}, Seq #{child_node.insertion_sequence}) prioritized over Parent (P{parent_node.priority}, Seq #{parent_node.insertion_sequence})"
                )
                swaps.append(swap_event)
                index = parent_idx
            else:
                break

        return comparisons, swaps

    @staticmethod
    def get_priority_label(prio: int) -> str:
        labels = {
            1: "Critical",
            2: "High",
            3: "Medium",
            4: "Low",
            5: "Background"
        }
        return labels.get(prio, f"P{prio}")

    def to_logical_execution_order(self) -> List[Dict[str, Any]]:
        """
        Non-mutating view of the eligible tasks in logical dispatch order.
        Calculated by projecting the tasks sorted by the scheduling key:
        (priority, insertion_sequence, created_at, task_id).
        Does NOT mutate or alter the actual heap array.
        """
        with self._lock:
            sorted_nodes = sorted(self.heap, key=lambda n: n.key)
            return [
                {
                    "execution_order": idx + 1,
                    "task_id": node.task_id,
                    "title": node.data.get("title", f"Task #{node.task_id}"),
                    "priority": node.priority,
                    "priority_label": self.get_priority_label(node.priority),
                    "insertion_sequence": node.insertion_sequence,
                    "heap_index": self.index_map.get(node.task_id, -1),
                    "category": node.data.get("category", "General"),
                    "due_date": node.data.get("due_date", ""),
                    "is_next": idx == 0
                }
                for idx, node in enumerate(sorted_nodes)
            ]

    def _sift_down(self, index: int):
        """
        Restores min-heap property downward using HeapNode.key.
        Logs each comparison of children, comparison with parent, and swap.
        Time Complexity: O(log n)
        """
        size = len(self.heap)
        while True:
            smallest = index
            left = self.left_child_index(index)
            right = self.right_child_index(index)

            # Compare left and right children if both exist to select smaller scheduling key
            if left < size and right < size:
                left_node = self.heap[left]
                right_node = self.heap[right]
                left_wins = left_node < right_node
                preferred_child = left if left_wins else right
                pref_node = self.heap[preferred_child]
                self.last_operation_steps.append({
                    "action": "compare_children",
                    "parent_index": index,
                    "left_index": left,
                    "left_task": left_node.data.get("title", f"Task #{left_node.task_id}"),
                    "left_priority": left_node.priority,
                    "left_sequence": left_node.insertion_sequence,
                    "right_index": right,
                    "right_task": right_node.data.get("title", f"Task #{right_node.task_id}"),
                    "right_priority": right_node.priority,
                    "right_sequence": right_node.insertion_sequence,
                    "selected_child_index": preferred_child,
                    "selected_task": pref_node.data.get("title", f"Task #{pref_node.task_id}"),
                    "reason": (
                        f"Compared children: Left [{left}] (P{left_node.priority}, Seq #{left_node.insertion_sequence}) "
                        f"vs Right [{right}] (P{right_node.priority}, Seq #{right_node.insertion_sequence}). "
                        f"Selected Child [{preferred_child}] with smaller scheduling key."
                    )
                })

            if left < size and self.heap[left] < self.heap[smallest]:
                smallest = left

            if right < size and self.heap[right] < self.heap[smallest]:
                smallest = right

            if smallest != index:
                parent_node = self.heap[index]
                child_node = self.heap[smallest]
                self.last_operation_steps.append({
                    "action": "compare_parent_child",
                    "parent_index": index,
                    "parent_task": parent_node.data.get("title", f"Task #{parent_node.task_id}"),
                    "parent_priority": parent_node.priority,
                    "child_index": smallest,
                    "child_task": child_node.data.get("title", f"Task #{child_node.task_id}"),
                    "child_priority": child_node.priority,
                    "swap_needed": True,
                    "reason": f"Parent at [{index}] (P{parent_node.priority}) > Child at [{smallest}] (P{child_node.priority}). Swap required downward."
                })

                self._swap(
                    index, smallest,
                    reason=f"Swapped parent downward from [{index}] to [{smallest}]; promoted child [{smallest}] to [{index}]"
                )
                index = smallest
            else:
                if left < size:
                    parent_node = self.heap[index]
                    self.last_operation_steps.append({
                        "action": "compare_parent_child",
                        "parent_index": index,
                        "parent_task": parent_node.data.get("title", f"Task #{parent_node.task_id}"),
                        "parent_priority": parent_node.priority,
                        "child_index": left,
                        "swap_needed": False,
                        "reason": f"Parent at [{index}] has smaller or equal scheduling key than children. Sift-down complete."
                    })
                break

    def _generate_insertion_explanation(self, title: str, priority: int,
                                        initial_idx: int, final_idx: int,
                                        comparisons: List[Dict[str, Any]],
                                        swaps: List[Dict[str, Any]]) -> str:
        """
        Generates a 100% truthful explanation narrative generated strictly from the
        actual comparisons and swaps performed. Does not invent swaps or comparisons.
        """
        if initial_idx == 0:
            return (
                f"Task '{title}' (P{priority}) inserted as the root at heap index 0 into an empty queue. "
                "No parent comparison needed. Min-heap property immediately satisfied."
            )

        narrative = [f"Task inserted at heap index {initial_idx}."]

        if not swaps:
            comp = comparisons[0]
            narrative.append(
                f"Compared with its parent at index {comp['parent_index']} "
                f"(Parent P{comp['parent_priority']} <= Child P{comp['child_priority']}). "
                f"No swap needed; min-heap property satisfied. Task settled at index {initial_idx}."
            )
            return " ".join(narrative)

        for i, swap in enumerate(swaps):
            comp = comparisons[i] if i < len(comparisons) else None
            p_detail = f" (Parent P{comp['parent_priority']} > Child P{comp['child_priority']})" if comp else ""
            narrative.append(
                f"Compared with parent at index {swap['index_b']}{p_detail}. "
                f"Swapped upward from index {swap['index_a']} to index {swap['index_b']}."
            )

        if len(comparisons) > len(swaps):
            last_comp = comparisons[-1]
            narrative.append(
                f"Compared with parent at index {last_comp['parent_index']} "
                f"(Parent P{last_comp['parent_priority']} <= Child P{last_comp['child_priority']}). "
                f"Min-heap property satisfied."
            )

        if final_idx == 0:
            narrative.append("Task promoted to root index 0 as highest priority in the queue to maintain the min-heap property.")
        else:
            narrative.append(f"Task settled at heap index {final_idx} to maintain the min-heap property.")

        return " ".join(narrative)

    def insert(self, task_id: int, priority: int, created_at: float, data: Dict[str, Any], insertion_sequence: int = 0) -> InsertionTrace:
        """
        Enqueues a task into the Priority Queue.
        1. Appends task to the end of the array.
        2. Sifts up to restore the min-heap invariant while tracking all comparisons and swaps.
        Time Complexity: O(log n)
        Returns InsertionTrace object with metrics and exact explanation narrative.
        """
        with self._lock:
            if task_id in self.index_map:
                raise ValueError(f"Task #{task_id} is already in the priority queue.")

            self.last_operation_steps = []
            new_node = HeapNode(task_id, priority, created_at, data, insertion_sequence=insertion_sequence)
            self.heap.append(new_node)
            new_index = len(self.heap) - 1
            self.index_map[task_id] = new_index

            title = data.get("title", f"Task #{task_id}")
            self.last_operation_steps.append({
                "action": "insert",
                "index": new_index,
                "task": title,
                "priority": priority,
                "reason": f"Appended at array index [{new_index}]; initiating sift-up"
            })

            comparisons, swaps = self._sift_up(new_index)
            final_index = self.index_map[task_id]

            explanation = self._generate_insertion_explanation(
                title=title,
                priority=priority,
                initial_idx=new_index,
                final_idx=final_index,
                comparisons=comparisons,
                swaps=swaps
            )

            self.last_operation_steps.append({
                "action": "sift_up_complete",
                "final_index": final_index,
                "is_root": final_index == 0,
                "reason": f"Sift-up complete. Task settled at heap index [{final_index}]."
            })

            trace = InsertionTrace(
                steps=list(self.last_operation_steps),
                initial_index=new_index,
                final_index=final_index,
                comparisons_count=len(comparisons),
                swaps_count=len(swaps),
                explanation=explanation,
                comparisons=comparisons,
                swaps=swaps
            )
            return trace

    def extract_min(self) -> Tuple[Optional[HeapNode], List[Dict[str, Any]]]:
        """
        De-queues and returns the highest-priority task from root.
        1. Identifies and extracts root (index 0).
        2. Moves last array element to root.
        3. Sifts down to restore min-heap invariant.
        Time Complexity: O(log n)
        """
        with self._lock:
            if self.is_empty():
                return None, []

            self.last_operation_steps = []
            min_node = self.heap[0]

            self.last_operation_steps.append({
                "action": "extract_start",
                "index": 0,
                "task_id": min_node.task_id,
                "task": min_node.data.get("title", f"Task #{min_node.task_id}"),
                "priority": min_node.priority,
                "insertion_sequence": min_node.insertion_sequence,
                "reason": f"Root task #{min_node.task_id} (P{min_node.priority}) identified as next eligible task for execution."
            })

            self.last_operation_steps.append({
                "action": "remove_root",
                "index": 0,
                "task_id": min_node.task_id,
                "task": min_node.data.get("title", f"Task #{min_node.task_id}"),
                "reason": f"Removed root task #{min_node.task_id} from heap root."
            })

            last_node = self.heap.pop()
            del self.index_map[min_node.task_id]

            if not self.is_empty():
                self.heap[0] = last_node
                self.index_map[last_node.task_id] = 0

                self.last_operation_steps.append({
                    "action": "replace_root",
                    "index": 0,
                    "task_id": last_node.task_id,
                    "task": last_node.data.get("title", f"Task #{last_node.task_id}"),
                    "priority": last_node.priority,
                    "insertion_sequence": last_node.insertion_sequence,
                    "reason": f"Moved last array leaf (Task #{last_node.task_id}) to root index [0]; initiating sift-down."
                })

                self._sift_down(0)

                self.last_operation_steps.append({
                    "action": "sift_down_complete",
                    "final_root_task": self.heap[0].data.get("title", f"Task #{self.heap[0].task_id}"),
                    "final_root_priority": self.heap[0].priority,
                    "reason": f"Sift-down complete. Root is now Task #{self.heap[0].task_id} (P{self.heap[0].priority}). Min-heap property satisfied."
                })
            else:
                self.last_operation_steps.append({
                    "action": "queue_now_empty",
                    "reason": "Extracted the last remaining task. Priority queue is now empty."
                })

            return min_node, list(self.last_operation_steps)

    def update_priority(self, task_id: int, new_priority: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Updates task priority (Decrease-Key or Increase-Key).
        Time Complexity: O(log n) via O(1) index map.
        """
        with self._lock:
            if task_id not in self.index_map:
                return False, []

            self.last_operation_steps = []
            idx = self.index_map[task_id]
            old_priority = self.heap[idx].priority
            self.heap[idx].priority = new_priority
            self.heap[idx].data["priority"] = new_priority

            self.last_operation_steps.append({
                "action": "update_priority",
                "index": idx,
                "task": self.heap[idx].data.get("title", f"Task #{task_id}"),
                "old_priority": old_priority,
                "new_priority": new_priority,
                "reason": f"Priority updated from P{old_priority} to P{new_priority}"
            })

            if new_priority < old_priority:
                # Urgency increased -> Sift up
                self._sift_up(idx)
            elif new_priority > old_priority:
                # Urgency decreased -> Sift down
                self._sift_down(idx)

            return True, list(self.last_operation_steps)

    def remove(self, task_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Removes an arbitrary task from the queue.
        Time Complexity: O(log n).
        """
        with self._lock:
            if task_id not in self.index_map:
                return False, []

            self.last_operation_steps = []
            idx = self.index_map[task_id]
            removed_node = self.heap[idx]

            self.last_operation_steps.append({
                "action": "remove",
                "index": idx,
                "task": removed_node.data.get("title", f"Task #{task_id}"),
                "reason": f"Task #{task_id} canceled and removed from heap"
            })

            last_node = self.heap.pop()
            del self.index_map[task_id]

            if idx < len(self.heap):
                self.heap[idx] = last_node
                self.index_map[last_node.task_id] = idx

                parent_idx = self.parent_index(idx)
                if idx > 0 and self.heap[idx] < self.heap[parent_idx]:
                    self._sift_up(idx)
                else:
                    self._sift_down(idx)

            return True, list(self.last_operation_steps)

    def is_valid_heap(self) -> bool:
        """Validates that min-heap property holds for all parent-child pairs."""
        with self._lock:
            n = len(self.heap)
            for i in range(n // 2):
                left = self.left_child_index(i)
                right = self.right_child_index(i)

                if left < n and self.heap[i] > self.heap[left]:
                    return False
                if right < n and self.heap[i] > self.heap[right]:
                    return False
            return True

    def to_array(self) -> List[Dict[str, Any]]:
        """Serialized contiguous array buffer with index relations."""
        with self._lock:
            res = []
            for i, node in enumerate(self.heap):
                parent = self.parent_index(i) if i > 0 else None
                left = self.left_child_index(i) if self.left_child_index(i) < len(self.heap) else None
                right = self.right_child_index(i) if self.right_child_index(i) < len(self.heap) else None

                res.append({
                    "index": i,
                    "task_id": node.task_id,
                    "title": node.data.get("title", "Untitled Task"),
                    "description": node.data.get("description", ""),
                    "category": node.data.get("category", "General"),
                    "priority": node.priority,
                    "priority_label": self.get_priority_label(node.priority),
                    "due_date": node.data.get("due_date", ""),
                    "insertion_sequence": node.insertion_sequence,
                    "created_at": node.created_at,
                    "estimated_duration": node.data.get("estimated_duration", 10),
                    "parent_index": parent,
                    "left_child_index": left,
                    "right_child_index": right,
                    "is_root": i == 0
                })
            return res

    def to_tree_structure(self) -> Dict[str, Any]:
        """Builds hierarchical tree structure for SVG rendering."""
        with self._lock:
            if self.is_empty():
                return {}

            def build_node(i: int, depth: int = 0) -> Optional[Dict[str, Any]]:
                if i >= len(self.heap):
                    return None
                node = self.heap[i]
                left_i = self.left_child_index(i)
                right_i = self.right_child_index(i)

                children = []
                if left_i < len(self.heap):
                    left_tree = build_node(left_i, depth + 1)
                    if left_tree:
                        left_tree["branch"] = "L (2i+1)"
                        children.append(left_tree)
                if right_i < len(self.heap):
                    right_tree = build_node(right_i, depth + 1)
                    if right_tree:
                        right_tree["branch"] = "R (2i+2)"
                        children.append(right_tree)

                return {
                    "index": i,
                    "task_id": node.task_id,
                    "title": node.data.get("title", "Untitled"),
                    "description": node.data.get("description", ""),
                    "category": node.data.get("category", "General"),
                    "priority": node.priority,
                    "priority_label": self.get_priority_label(node.priority),
                    "due_date": node.data.get("due_date", ""),
                    "insertion_sequence": node.insertion_sequence,
                    "created_at": node.created_at,
                    "depth": depth,
                    "is_root": i == 0,
                    "children": children
                }

            return build_node(0) or {}
