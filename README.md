# PriorityFlow &mdash; SaaS Binary Min-Heap Priority Queue Engine

A production-grade, SaaS-style priority queue and background task orchestration platform built to demonstrate advanced **Data Structures and Algorithms (DSA)** in a real-world enterprise setting.

Powered by: **Python (Flask), SQLite, HTML5, Vanilla CSS3, JavaScript (SVG & D3-style layouts), Chart.js, and pytest**.

---

## 🎨 SaaS Design & Theme
- **Color Direction:** Soft neutral background (`#f8fafc`), crisp white cards (`#ffffff`), deep navy typography (`#0f172a`), and restrained indigo/blue accents (`#4f46e5`, `#2563eb`).
- **Typography:** Inter for high-legibility UI text, Outfit for brand and card headers, JetBrains Mono for memory arrays and complexity math.
- **Micro-Interactions:** Subtle shadows, rounded corners (`12px`), animated node transitions, parent/child hover highlighting, and live operation swap tracking.

---

## 🧭 Complete Sidebar Navigation (All 7 Sections Active)

Every navigation item and button in PriorityFlow is fully functional with live backend endpoints:

1. **Overview (`section-overview`)**
   - Executive KPI cards: Active In-Heap Queue depth, Worker cluster utilization, Lifetime completed tasks, Min-Heap invariant health.
   - **Spotlight Root Task Card:** Immediate visibility into the highest-priority root node waiting at index `[0]`.
   - **Execution Worker Pool Grid:** Live status of distributed worker nodes with instant task completion.
   - **Heap Mutation Audit Trail:** Chronological log of recent sift-up and sift-down operations.
   - Quick header actions: **New Task**, **Dispatch Root (Extract-Min)**, and **Simulate Burst**.

2. **Create Task (`section-create-task`)**
   - Ingestion form with workload classification (Critical Infrastructure, Payment Gateway, Security Patch, Data Pipeline, Search Cluster, Background Job).
   - Priority Tier Selector with visual radio cards ($P1$ Critical to $P5$ Background).
   - **One-Click Workload Presets:** Pre-fills real cloud workloads (e.g., *Database Primary Failover [P1]*, *OpenSSL Hotpatch [P2]*, *Nightly Revenue ETL [P3]*).
   - **Live Sift-Up Output:** Displays the exact swap step trace immediately after enqueuing.

3. **Live Priority Queue (`section-live-queue`)**
   - **Dynamic SVG Binary Tree Visualizer:** Computes $(x, y)$ coordinates per tree level, draws branch labels ($L: 2i+1, R: 2i+2$), and highlights the root node.
   - **Parent/Child Relationship Highlighting:** Hovering any node highlights its parent $\lfloor(i-1)/2\rfloor$ in amber and children in cyan.
   - **Contiguous Array RAM Buffer (`heap[]`):** Demonstrates how the binary tree is stored sequentially in continuous memory.
   - **Priority Tuning Modal:** Clicking any node allows instant Decrease-Key or Increase-Key re-prioritization.

4. **Execution Simulator (`section-simulator`)**
   - **Automated Dispatch Loop Toggle:** Start/pause automated background ticker that pops the root task and assigns it to an idle worker every 3 seconds.
   - **Single Step Tick Button:** Dispatches exactly 1 task on demand.
   - **Traffic Spike Trigger:** Injects a burst of 5 enterprise tasks simultaneously to demonstrate root preemption.
   - **Worker Concurrency Matrix:** Live monitoring of worker node memory and execution duration.

5. **Task History (`section-history`)**
   - Filterable, searchable table displaying all tasks across their lifecycle (`QUEUED`, `PROCESSING`, `COMPLETED`, `CANCELLED`).
   - Real-time search across titles, categories, and notes.
   - Dropdown filters for Status and Workload Category.
   - **Export Tasks (JSON):** Downloads `priorityflow_tasks_export.json` for data portability.

6. **Performance Analytics (`section-analytics`)**
   - **Priority Distribution Donut Chart:** Visualizes distribution of active workloads across $P1$ through $P5$.
   - **Average Wait Latency Bar Chart:** Proves the priority queue SLA guarantee ($P1$ critical tasks wait $<1\text{s}$, whereas $P5$ background tasks wait until cluster resources are idle).
   - Queue depth and throughput telemetry.

7. **About Project (`section-about`)**
   - Comprehensive DSA college presentation notes:
     - Mathematical explanation of why a Binary Min-Heap is superior to sorting arrays.
     - Formal Time Complexity Matrix ($\mathcal{O}(1)$ peek, $\mathcal{O}(\log n)$ insert/extract).
     - Continuous array index formulas.
     - **Live Python `heapq` Parity Verification:** Real-time side-by-side verification comparing our custom `BinaryMinHeap` class with Python's built-in `heapq` library.

---

## ⚡ Data Structures & Algorithms Complexity

| Operation | PriorityFlow Min-Heap | Unsorted Array | Sorted Array |
|---|---|---|---|
| **Peek Root Task** | **$\mathcal{O}(1)$** | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ |
| **Insert / Enqueue** | **$\mathcal{O}(\log n)$** | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ |
| **Extract-Min / Dispatch** | **$\mathcal{O}(\log n)$** | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ |
| **Update Priority (Sift)** | **$\mathcal{O}(\log n)$** *(via $\mathcal{O}(1)$ index map)* | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |
| **Space Complexity** | **$\mathcal{O}(n)$** (contiguous RAM) | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |

### Array Representation Index Formulas
- $\text{Parent}(i) = \left\lfloor \frac{i - 1}{2} \right\rfloor$
- $\text{Left Child}(i) = 2i + 1$
- $\text{Right Child}(i) = 2i + 2$
- **Min-Heap Invariant:** $A[\text{Parent}(i)] \le A[i] \quad \forall \; i > 0$

---

## 🚀 Running the Project

### 1. Run Automated Test Suite (`pytest`)
```bash
pytest -v
```
All 33 unit and integration tests validate the data structure, database persistence, REST endpoints, and simulator lifecycle.

### 2. Start the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```
