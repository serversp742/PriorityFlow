/**
 * PriorityFlow - SaaS Application Controller
 * ==========================================
 * Orchestrates:
 * 1. Overview Dashboard with 100% real data from SQLite (8 KPI metrics, next task,
 *    priority distribution chart, task status distribution chart, recent events).
 * 2. Quick Add Task modal and Execute Next Task dispatching with live updates.
 * 3. Professional Empty State with Seed Sample Tasks action.
 * 4. Binary Min-Heap SVG tree visualizer & contiguous RAM array.
 * 5. Execution Simulator, Task History table, Analytics, and DSA verification.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Visualizers & Chart Managers
    const visualizer = new HeapVisualizer('live-heap-svg', 'live-array-strip', 'live-tree-trace-steps', 'logical-order-list');
    const chartsManager = new ChartsManager();

    // 2. State & Flags
    let currentHeapArray = [];
    let isAutoDispatchRunning = false;
    let autoDispatchTimer = null;
    let isSubmitting = false;
    let activeSimTask = null;
    let simStopwatchTimer = null;

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatDuration(sec) {
        if (sec === undefined || sec === null || isNaN(sec)) return '0.0s';
        if (sec < 60) return `${sec.toFixed(1)}s`;
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}m ${s.toString().padStart(2, '0')}s`;
    }

    // Presets dictionary for Create Task tab (Priorities: 1 = Critical, 2 = High, 3 = Medium, 4 = Low)
    const presets = {
        failover: {
            title: 'Database Primary Replica Failover',
            category: 'Critical Infrastructure',
            priority: '1',
            description: 'Automated health check alert: Master node heartbeat lost. Immediate failover required.'
        },
        stripe: {
            title: 'Stripe Webhook Gateway Reconciliation',
            category: 'Payment Gateway',
            priority: '2',
            description: 'SLA Risk: Unmatched subscription invoice webhooks requiring manual verification.'
        },
        cve: {
            title: 'Zero-Day OpenSSL Security Patch Hotpatch',
            category: 'Security Patch',
            priority: '2',
            description: 'CVE-2026-1184 edge proxy hotpatching to mitigate zero-day memory leak.'
        },
        etl: {
            title: 'ETL Data Pipeline: Daily Revenue Aggregation',
            category: 'Data Pipeline',
            priority: '3',
            description: 'Daily scheduled Snowflake warehouse transformation and dimensional metrics computation.'
        },
        search: {
            title: 'Algolia Search Replica Re-sharding & Indexing',
            category: 'Search Cluster',
            priority: '4',
            description: 'Background shard re-balancing across replica cluster. Deferrable until idle.'
        }
    };

    // Wire Rapid Enterprise Presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const presetKey = btn.getAttribute('data-preset');
            const p = presets[presetKey];
            if (!p) return;
            const titleInput = document.getElementById('task-title');
            const categorySelect = document.getElementById('task-category');
            const descInput = document.getElementById('task-description');
            if (titleInput) titleInput.value = p.title;
            if (categorySelect) categorySelect.value = p.category;
            if (descInput) descInput.value = p.description || '';
            const radio = document.querySelector(`input[name="task-priority"][value="${p.priority}"]`);
            if (radio) radio.checked = true;
        });
    });

    // ---------------------------------------------------------
    // Sidebar Navigation (7 Sections)
    // ---------------------------------------------------------
    const navItems = document.querySelectorAll('.nav-item');
    const sectionViews = document.querySelectorAll('.section-view');
    const headerTitle = document.getElementById('header-section-title');

    function switchSection(targetId) {
        navItems.forEach(item => {
            if (item.getAttribute('data-target') === targetId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        sectionViews.forEach(sec => {
            if (sec.id === targetId) {
                sec.classList.add('active');
            } else {
                sec.classList.remove('active');
            }
        });

        const activeNav = document.querySelector(`.nav-item[data-target="${targetId}"]`);
        if (activeNav && headerTitle) {
            headerTitle.innerText = activeNav.innerText.trim().split('\n')[0];
        }

        if (targetId === 'section-overview') {
            fetchOverview();
        } else if (targetId === 'section-history') {
            fetchTaskHistory();
        } else if (targetId === 'section-analytics') {
            fetchAnalytics();
        } else if (targetId === 'section-live-queue') {
            fetchHeapState();
        } else if (targetId === 'section-simulator') {
            fetchSimulatorState();
        }
    }

    navItems.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-target');
            if (target) switchSection(target);
        });
    });

    // ---------------------------------------------------------
    // OVERVIEW: Real Data from SQLite & Min-Heap
    // ---------------------------------------------------------

    async function fetchOverview() {
        try {
            const res = await fetch('/api/overview');
            const result = await res.json();
            if (result.status !== 'success') return;

            const data = result.data;

            // 1. Handle Empty State vs Active Data State
            const emptyStateBox = document.getElementById('overview-empty-state');
            const contentWrapper = document.getElementById('overview-content-wrapper');

            if (data.is_empty) {
                if (emptyStateBox) emptyStateBox.style.display = 'block';
                if (contentWrapper) contentWrapper.style.display = 'none';
                document.getElementById('sidebar-queue-badge').innerText = '0';
                return;
            } else {
                if (emptyStateBox) emptyStateBox.style.display = 'none';
                if (contentWrapper) contentWrapper.style.display = 'block';
            }

            // 2. Update 8 Real-Time KPI Metric Cards
            document.getElementById('stat-total-tasks').innerText = data.total_tasks;
            document.getElementById('stat-pending-tasks').innerText = data.pending_tasks;
            document.getElementById('stat-in-progress-tasks').innerText = data.in_progress_tasks;
            document.getElementById('stat-completed-tasks').innerText = data.completed_tasks;
            document.getElementById('stat-critical-tasks').innerText = data.critical_priority_tasks;
            document.getElementById('stat-queue-size').innerText = data.current_queue_size;
            document.getElementById('stat-total-inserts').innerText = data.total_inserts;
            document.getElementById('stat-total-extractions').innerText = data.total_extractions;

            // Sidebar Queue Badge
            document.getElementById('sidebar-queue-badge').innerText = data.current_queue_size;

            // 3. Update Next Task to be Executed (Spotlight Card)
            const nextBadge = document.getElementById('next-task-badge');
            const nextTitle = document.getElementById('next-task-title');
            const nextMeta = document.getElementById('next-task-meta');
            const nextNotes = document.getElementById('next-task-notes');
            const nextBtn = document.getElementById('btn-spotlight-execute-next');

            if (data.next_task) {
                const nt = data.next_task;
                const createdTime = new Date(nt.created_at * 1000).toLocaleTimeString();
                nextBadge.innerHTML = `NEXT TASK IN LINE &bull; P${nt.priority}`;
                nextBadge.className = `badge badge-p${nt.priority}`;
                nextTitle.innerText = nt.title;
                nextMeta.innerText = `Category: ${nt.category} &bull; Est. Duration: ${nt.estimated_duration}s &bull; Queued: ${createdTime}`;
                nextNotes.innerText = nt.notes ? `Context: ${nt.notes}` : 'No operational notes provided.';
                if (nextBtn) {
                    nextBtn.disabled = false;
                    nextBtn.innerText = 'Execute Next Task';
                }
            } else {
                nextBadge.innerHTML = 'QUEUE EMPTY';
                nextBadge.className = 'badge badge-queued';
                nextTitle.innerText = 'No tasks currently waiting in queue';
                nextMeta.innerText = 'All tasks have been processed or cancelled. Enqueue a task to continue.';
                nextNotes.innerText = '';
                if (nextBtn) {
                    nextBtn.disabled = true;
                    nextBtn.innerText = 'Queue Empty';
                }
            }

            // 4. Update Overview Charts (Priority & Status Distributions)
            chartsManager.updateOverviewCharts(data.priority_distribution, data.status_distribution);

            // 5. Update Recent Execution Events
            renderRecentEvents(data.recent_events || []);

        } catch (err) {
            console.error('Failed to fetch overview metrics:', err);
        }
    }

    function renderRecentEvents(events) {
        const container = document.getElementById('overview-events-container');
        if (!container) return;

        if (events.length === 0) {
            container.innerHTML = '<span class="empty-state-box">No execution events recorded yet.</span>';
            return;
        }

        container.innerHTML = events.slice(0, 8).map(ev => {
            const timeStr = new Date(ev.timestamp * 1000).toLocaleTimeString();
            let opColor = 'var(--brand-indigo)';
            if (ev.operation === 'EXTRACT_MIN' || ev.operation === 'AUTO_DISPATCH') opColor = '#0284c7';
            else if (ev.operation === 'COMPLETE') opColor = '#10b981';
            else if (ev.operation === 'CANCEL' || ev.operation === 'DELETE') opColor = '#ef4444';
            else if (ev.operation === 'UPDATE_PRIORITY') opColor = '#f59e0b';

            return `
                <div style="background: var(--bg-surface-elevated); padding: 10px 14px; border-radius: var(--radius-sm); border-left: 3px solid ${opColor}; display: flex; justify-content: space-between; align-items: center; gap: 12px;">
                    <div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: var(--text-main);">${ev.details}</div>
                        <span style="font-family: var(--font-mono); font-size: 0.7rem; color: ${opColor}; font-weight: 700;">${ev.operation}</span>
                    </div>
                    <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); white-space: nowrap;">${timeStr}</span>
                </div>
            `;
        }).join('');
    }

    // ---------------------------------------------------------
    // Execution Actions: Quick Add, Execute Next, Seed, Clear
    // ---------------------------------------------------------

    // Quick Add Modal
    const quickAddModal = document.getElementById('modal-quick-add-task');
    const formQuickAdd = document.getElementById('quick-add-task-form');

    function openQuickAddModal() {
        if (quickAddModal) quickAddModal.classList.remove('hidden');
        document.getElementById('quick-task-title')?.focus();
    }

    function closeQuickAddModal() {
        if (quickAddModal) quickAddModal.classList.add('hidden');
        if (formQuickAdd) formQuickAdd.reset();
    }

    document.getElementById('btn-header-quick-add')?.addEventListener('click', openQuickAddModal);
    document.getElementById('btn-overview-quick-add')?.addEventListener('click', openQuickAddModal);
    document.getElementById('btn-live-quick-add')?.addEventListener('click', openQuickAddModal);
    document.getElementById('btn-empty-quick-add')?.addEventListener('click', openQuickAddModal);
    document.getElementById('btn-close-quick-add-modal')?.addEventListener('click', closeQuickAddModal);
    document.getElementById('btn-cancel-quick-add')?.addEventListener('click', closeQuickAddModal);

    // Form Submit: Quick Add Task
    if (formQuickAdd) {
        formQuickAdd.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (isSubmitting) return;

            const title = document.getElementById('quick-task-title').value.trim();
            const category = document.getElementById('quick-task-category').value;
            const priority = parseInt(document.getElementById('quick-task-priority').value) || 3;
            const dueDate = document.getElementById('quick-task-due-date')?.value || '';
            const description = document.getElementById('quick-task-description')?.value.trim() || '';

            if (!title || title.length < 2) {
                alert('Task title must be at least 2 characters long.');
                return;
            }

            isSubmitting = true;

            const payload = {
                title: title,
                category: category,
                priority: priority,
                description: description,
                due_date: dueDate
            };

            try {
                const res = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    closeQuickAddModal();
                    
                    // Fetch updated heap state for final snapshot and logical order
                    const heapRes = await fetch('/api/heap/state');
                    const heapData = await heapRes.json();
                    const finalHeap = heapData.array || [];
                    const initialSnapshot = JSON.parse(JSON.stringify(currentHeapArray));
                    currentHeapArray = finalHeap;

                    if (data.steps && data.steps.length > 0) {
                        visualizer.loadTrace(
                            data.steps,
                            initialSnapshot,
                            finalHeap,
                            'insert',
                            heapData.logical_order || []
                        );
                    } else {
                        visualizer.update(currentHeapArray, data.steps || [], heapData.logical_order || []);
                    }

                    fetchOverview();
                    fetchWorkers();
                    fetchTaskHistory();
                } else {
                    alert(data.message || 'Failed to add task.');
                }
            } catch (err) {
                console.error(err);
                alert('Network error adding task.');
            } finally {
                isSubmitting = false;
            }
        });
    }

    // Execute Next Task (Extract-Min)
    async function executeNextTask() {
        if (isSubmitting) return;
        isSubmitting = true;

        const initialHeapSnapshot = JSON.parse(JSON.stringify(currentHeapArray));

        try {
            const res = await fetch('/api/tasks/extract-next', { method: 'POST' });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                // Fetch fresh heap state to get the final snapshot and logical execution order
                const heapRes = await fetch('/api/heap/state');
                const heapData = await heapRes.json();
                const finalHeap = heapData.array || [];
                currentHeapArray = finalHeap;

                // Load real extraction trace into the interactive visualizer animation engine
                visualizer.loadTrace(
                    data.steps || [],
                    initialHeapSnapshot,
                    finalHeap,
                    'extract',
                    heapData.logical_order || []
                );

                fetchOverview();
                fetchWorkers();
                fetchTaskHistory();
                fetchSimulatorState();
            } else {
                alert(data.message || 'Queue is currently empty.');
            }
        } catch (err) {
            console.error('Dispatch error:', err);
        } finally {
            isSubmitting = false;
        }
    }

    document.getElementById('btn-header-execute-next')?.addEventListener('click', executeNextTask);
    document.getElementById('btn-overview-execute-next')?.addEventListener('click', executeNextTask);
    document.getElementById('btn-spotlight-execute-next')?.addEventListener('click', executeNextTask);
    document.getElementById('btn-live-execute-next')?.addEventListener('click', executeNextTask);
    document.getElementById('btn-sim-execute-next')?.addEventListener('click', executeNextTask);
    document.getElementById('btn-card-execute-next')?.addEventListener('click', executeNextTask);

    // Seed Sample Tasks
    async function seedSampleTasks() {
        try {
            const res = await fetch('/api/tasks/seed-samples', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                refreshAll();
                fetchTaskHistory();
            }
        } catch (err) {
            console.error(err);
        }
    }

    document.getElementById('btn-overview-seed-samples')?.addEventListener('click', seedSampleTasks);
    document.getElementById('btn-empty-seed-samples')?.addEventListener('click', seedSampleTasks);
    document.getElementById('btn-anim-sample-tasks')?.addEventListener('click', seedSampleTasks);

    // Clear All Tasks (Empty State Testing)
    async function clearAllTasks() {
        if (!confirm('Clear all tasks from the SQLite database to verify the empty state?')) return;
        try {
            const res = await fetch('/api/tasks/clear-all', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                refreshAll();
                fetchTaskHistory();
            }
        } catch (err) {
            console.error(err);
        }
    }

    document.getElementById('btn-overview-clear-all')?.addEventListener('click', clearAllTasks);

    // ---------------------------------------------------------
    // API Data Fetching: Heap State, Workers, Task History
    // ---------------------------------------------------------

    async function fetchHeapState() {
        try {
            const res = await fetch('/api/heap/state');
            const data = await res.json();
            if (data.status === 'success') {
                currentHeapArray = data.array || [];
                visualizer.update(currentHeapArray, data.last_steps || [], data.logical_order || []);
            }
        } catch (err) {
            console.error('Failed to fetch heap state:', err);
        }
    }

    async function fetchWorkers() {
        try {
            const res = await fetch('/api/workers');
            const data = await res.json();
            if (data.status === 'success') {
                renderWorkersMatrix(data.workers || []);
            }
        } catch (err) {
            console.error('Failed to fetch workers:', err);
        }
    }

    async function fetchAnalytics() {
        try {
            const res = await fetch('/api/analytics');
            const data = await res.json();
            if (data.status === 'success') {
                chartsManager.updateAnalytics(data.analytics);
            }
        } catch (err) {
            console.error('Failed to fetch analytics:', err);
        }
    }

    async function fetchTaskHistory() {
        const statusFilter = document.getElementById('table-status-filter')?.value || 'ALL';
        const categoryFilter = document.getElementById('table-category-filter')?.value || 'ALL';
        const searchVal = document.getElementById('table-search-input')?.value || '';

        let url = `/api/tasks?status=${encodeURIComponent(statusFilter)}&category=${encodeURIComponent(categoryFilter)}`;
        if (searchVal.trim()) {
            url += `&search=${encodeURIComponent(searchVal.trim())}`;
        }

        try {
            const res = await fetch(url);
            const data = await res.json();
            if (data.status === 'success') {
                renderTaskTable(data.tasks || []);
            }
        } catch (err) {
            console.error('Failed to fetch task history:', err);
        }
    }

    function refreshAll() {
        fetchOverview();
        fetchHeapState();
        fetchWorkers();
        fetchSimulatorState();
    }

    // ---------------------------------------------------------
    // Render Functions: Workers & Task History Table
    // ---------------------------------------------------------

    function renderWorkersMatrix(workers) {
        const simulatorContainer = document.getElementById('simulator-workers-container');
        if (!simulatorContainer) return;

        simulatorContainer.innerHTML = workers.map(w => {
            const isBusy = w.status === 'BUSY';
            const statusBadge = isBusy 
                ? '<span class="badge badge-processing">BUSY &bull; RUNNING</span>' 
                : '<span class="badge badge-completed">IDLE &bull; READY</span>';

            return `
                <div class="worker-node-box ${isBusy ? 'busy' : 'idle'}">
                    <div class="worker-header">
                        <div>
                            <div class="worker-name">${w.name}</div>
                            <div class="worker-region">${w.region}</div>
                        </div>
                        ${statusBadge}
                    </div>

                    ${isBusy ? `
                        <div class="worker-task-info">
                            <div>
                                <strong style="color: var(--text-main); display: block;">${w.current_task_title || 'Active Task'}</strong>
                                <span class="badge badge-p${w.current_task_priority}">P${w.current_task_priority}</span>
                                <small style="color: var(--text-muted); margin-left: 6px;">${w.current_task_category || ''}</small>
                            </div>
                            <button class="btn btn-outline btn-sm" onclick="window.completeTask(${w.current_task_id})">
                                Complete
                            </button>
                        </div>
                    ` : `
                        <div style="font-size: 0.75rem; color: var(--success); font-style: italic;">
                            Ready for immediate execution dispatch. (${w.completed_count || 0} completed)
                        </div>
                    `}
                </div>
            `;
        }).join('');
    }

    function renderTaskTable(tasks) {
        const tbody = document.getElementById('task-table-body');
        if (!tbody) return;

        if (tasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="empty-state-box">No tasks found matching your filter criteria.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = tasks.map(t => {
            const dateStr = new Date(t.created_at * 1000).toLocaleTimeString();
            const statusClass = `badge-${t.status.toLowerCase()}`;

            let actionsHtml = '';
            if (t.status === 'QUEUED') {
                actionsHtml = `
                    <button class="btn btn-outline btn-sm" onclick="window.openPriorityModal(${t.id}, '${t.title.replace(/'/g, "\\'")}', ${t.priority})">
                        Re-prioritize
                    </button>
                    <button class="btn btn-outline btn-sm" style="color: #dc2626;" onclick="window.deleteTask(${t.id})">
                        Delete
                    </button>
                `;
            } else if (t.status === 'PROCESSING') {
                actionsHtml = `
                    <button class="btn btn-outline btn-sm" onclick="window.completeTask(${t.id})">
                        Complete
                    </button>
                `;
            } else {
                actionsHtml = `<span style="color: var(--text-muted); font-size: 0.75rem;">Archived</span>`;
            }

            return `
                <tr>
                    <td style="font-family: var(--font-mono); font-weight: 600; color: var(--text-muted);">#${t.id}</td>
                    <td>
                        <strong>${t.title}</strong>
                        ${t.notes ? `<div style="font-size: 0.72rem; color: var(--text-muted);">${t.notes}</div>` : ''}
                    </td>
                    <td><span class="badge badge-queued">${t.category}</span></td>
                    <td><span class="badge badge-p${t.priority}">P${t.priority}</span></td>
                    <td><span class="badge ${statusClass}">${t.status}</span></td>
                    <td style="font-size: 0.8rem; color: var(--text-secondary);">${t.assigned_worker || '-'}</td>
                    <td style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">${dateStr}</td>
                    <td><div class="table-action-group">${actionsHtml}</div></td>
                </tr>
            `;
        }).join('');
    }

    // ---------------------------------------------------------
    // Execution Simulator Controller: Active Task, Timers, Lifecycle
    // ---------------------------------------------------------

    async function fetchSimulatorState() {
        try {
            const res = await fetch('/api/simulator/state');
            const data = await res.json();
            if (data.status === 'success') {
                renderSimulatorView(data);
            }
        } catch (err) {
            console.error('Failed to fetch simulator state:', err);
        }
    }

    function startLiveStopwatch(startedAt) {
        if (simStopwatchTimer) {
            clearInterval(simStopwatchTimer);
            simStopwatchTimer = null;
        }

        const updateStopwatch = () => {
            const el = document.getElementById('sim-live-stopwatch');
            if (!el || !startedAt) return;
            const nowSec = Date.now() / 1000;
            const elapsed = Math.max(0, nowSec - startedAt);
            el.innerText = formatDuration(elapsed);
        };

        updateStopwatch();
        simStopwatchTimer = setInterval(updateStopwatch, 500);
    }

    function renderSimulatorView(data) {
        activeSimTask = data.active_task;
        const remainingCount = data.remaining_pending_count || 0;

        // 1. Remaining pending tasks badge
        const remainingBadge = document.getElementById('sim-remaining-pending-badge');
        if (remainingBadge) {
            remainingBadge.innerText = `${remainingCount} Pending in Queue`;
        }

        const emptyStateCard = document.getElementById('sim-empty-state');
        const taskContentBox = document.getElementById('sim-task-content-box');
        const statusBadge = document.getElementById('sim-task-status-badge');
        const btnSimComplete = document.getElementById('btn-sim-mark-completed');
        const btnCardComplete = document.getElementById('btn-card-mark-completed');
        const btnSimCancel = document.getElementById('btn-sim-cancel-task');
        const btnCardCancel = document.getElementById('btn-card-cancel-task');

        if (activeSimTask) {
            // Task is IN PROGRESS / PROCESSING
            if (emptyStateCard) emptyStateCard.style.display = 'none';

            if (statusBadge) {
                statusBadge.className = 'badge badge-processing';
                statusBadge.innerHTML = '<span class="pulse-indicator active" style="width: 7px; height: 7px; display: inline-block; margin-right: 5px;"></span> In Progress';
            }

            if (btnSimComplete) btnSimComplete.disabled = false;
            if (btnCardComplete) btnCardComplete.disabled = false;
            if (btnSimCancel) btnSimCancel.disabled = false;
            if (btnCardCancel) btnCardCancel.disabled = false;

            const prio = activeSimTask.priority;
            const prioLabel = activeSimTask.priority_label || (prio === 1 ? 'Critical' : prio === 2 ? 'High' : prio === 3 ? 'Medium' : 'Low');
            const startStr = activeSimTask.started_at ? new Date(activeSimTask.started_at * 1000).toLocaleString() : 'Just now';
            const algoTime = (activeSimTask.algorithm_duration_ms !== undefined && activeSimTask.algorithm_duration_ms !== null)
                ? Number(activeSimTask.algorithm_duration_ms).toFixed(4)
                : '0.0420';

            if (taskContentBox) {
                taskContentBox.innerHTML = `
                    <div class="sim-active-grid">
                        <div class="sim-task-main">
                            <div class="sim-task-heading">
                                <span class="sim-id-badge">#TASK-${activeSimTask.id}</span>
                                <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: var(--text-main);">${escapeHtml(activeSimTask.title)}</h2>
                            </div>

                            <div class="sim-task-desc-box">
                                <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">Task Description & Payload Context:</div>
                                <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5;">
                                    ${activeSimTask.description ? escapeHtml(activeSimTask.description) : '<em>No operational notes or description provided for this workload.</em>'}
                                </div>
                            </div>

                            <div class="sim-meta-pill-list">
                                <div class="sim-meta-pill">
                                    <strong>Priority:</strong>
                                    <span class="badge badge-p${prio}">P${prio} &bull; ${prioLabel}</span>
                                </div>
                                <div class="sim-meta-pill">
                                    <strong>Category:</strong>
                                    <span class="badge badge-queued">${escapeHtml(activeSimTask.category || 'General')}</span>
                                </div>
                                <div class="sim-meta-pill">
                                    <strong>Assigned Node:</strong>
                                    <span style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--brand-indigo);">${escapeHtml(activeSimTask.assigned_worker || 'cluster-node-1')}</span>
                                </div>
                                <div class="sim-meta-pill">
                                    <strong>Start Timestamp:</strong>
                                    <span style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-secondary);">${startStr}</span>
                                </div>
                            </div>
                        </div>

                        <div class="sim-timers-column">
                            <div class="sim-timer-card timer-algo">
                                <div class="sim-timer-title">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
                                    Priority Queue Algorithm Time
                                </div>
                                <div class="sim-timer-val">${algoTime} <span style="font-size: 0.85rem; font-weight: 600;">ms</span></div>
                                <div class="sim-timer-sub">Binary Min-Heap O(log n) Extract-Min operation latency</div>
                            </div>

                            <div class="sim-timer-card timer-realworld">
                                <div class="sim-timer-title">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
                                    Real-World Task Duration
                                </div>
                                <div class="sim-timer-val" id="sim-live-stopwatch">0.0s</div>
                                <div class="sim-timer-sub">Active working time spent on this task in cluster worker (stopwatch)</div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Start live ticking stopwatch
            startLiveStopwatch(activeSimTask.started_at);

        } else {
            // No active task currently running
            if (simStopwatchTimer) {
                clearInterval(simStopwatchTimer);
                simStopwatchTimer = null;
            }

            if (btnSimComplete) btnSimComplete.disabled = true;
            if (btnCardComplete) btnCardComplete.disabled = true;
            if (btnSimCancel) btnSimCancel.disabled = true;
            if (btnCardCancel) btnCardCancel.disabled = true;

            if (remainingCount === 0) {
                // Empty queue AND no active task -> Show friendly empty state
                if (emptyStateCard) emptyStateCard.style.display = 'block';
                if (statusBadge) {
                    statusBadge.className = 'badge badge-queued';
                    statusBadge.innerText = 'Queue Empty';
                }
                if (taskContentBox) {
                    taskContentBox.innerHTML = `
                        <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px dashed var(--border-color);">
                            <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 6px; color: var(--text-secondary);">No Workload Selected</div>
                            <p style="font-size: 0.82rem; margin: 0;">No active task is running, and no eligible pending tasks exist in the queue. Click "Seed Samples" or "Create Sample Tasks" to begin.</p>
                        </div>
                    `;
                }
            } else {
                // Queue has tasks waiting, but none currently selected/in progress
                if (emptyStateCard) emptyStateCard.style.display = 'none';
                if (statusBadge) {
                    statusBadge.className = 'badge badge-queued';
                    statusBadge.innerText = 'Idle &bull; Ready';
                }

                const next = data.next_eligible_task;
                const nextTitle = next ? escapeHtml(next.title) : 'Next queued workload';
                const nextPrio = next ? next.priority : '?';
                const nextLabel = next ? next.priority_label : `P${nextPrio}`;
                const nextSeq = next ? next.insertion_sequence : '?';

                if (taskContentBox) {
                    taskContentBox.innerHTML = `
                        <div class="sim-preview-box">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                                <span style="font-size: 0.75rem; font-weight: 700; color: var(--brand-indigo); text-transform: uppercase;">
                                    &bull; Ready for Execution Dispatch
                                </span>
                                <span class="badge badge-p${nextPrio}">Next Eligible: P${nextPrio} &bull; ${nextLabel} (Sequence #${nextSeq})</span>
                            </div>
                            <h3 style="margin: 0 0 8px 0; font-size: 1.15rem; color: var(--text-main);">${nextTitle}</h3>
                            <p style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.5; margin: 0 0 14px 0;">
                                ${next && next.description ? escapeHtml(next.description) : 'Currently residing at root [index 0] of the binary min-heap. Click <strong>"Execute Next Task"</strong> to extract from the Priority Queue and begin execution.'}
                            </p>
                            <div style="display: flex; gap: 8px;">
                                <button class="btn btn-primary btn-sm" onclick="document.getElementById('btn-sim-execute-next').click()">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                                    Execute Next Task Now
                                </button>
                            </div>
                        </div>
                    `;
                }
            }
        }

        // 2. Update Latest Algorithm Operation Details
        const latestOp = data.latest_operation;
        const latestOpText = document.getElementById('sim-latest-operation-text');
        if (latestOpText) {
            if (latestOp) {
                const timeStr = new Date(latestOp.timestamp * 1000).toLocaleTimeString();
                latestOpText.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
                        <span><strong>[${escapeHtml(latestOp.operation)}]</strong> ${escapeHtml(latestOp.details)}</span>
                        <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${timeStr}</span>
                    </div>
                `;
            } else {
                latestOpText.innerHTML = '<em>No recent algorithm operations recorded.</em>';
            }
        }

        // 3. Render Event logs in #simulator-event-logs
        const eventLogsBox = document.getElementById('simulator-event-logs');
        if (eventLogsBox && data.recent_events) {
            if (data.recent_events.length === 0) {
                eventLogsBox.innerHTML = '<span class="empty-state-box">No execution events recorded yet.</span>';
            } else {
                eventLogsBox.innerHTML = data.recent_events.map(ev => {
                    const tStr = new Date(ev.timestamp * 1000).toLocaleTimeString();
                    let opBadgeClass = 'badge-queued';
                    if (ev.operation === 'EXTRACT_MIN') opBadgeClass = 'badge-processing';
                    else if (ev.operation === 'COMPLETE') opBadgeClass = 'badge-completed';
                    else if (ev.operation === 'CANCEL' || ev.operation === 'DELETE') opBadgeClass = 'badge-p1';

                    return `
                        <div style="padding: 8px 12px; background: var(--bg-surface-elevated); border-radius: var(--radius-sm); border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                            <div>
                                <span class="badge ${opBadgeClass}" style="margin-right: 6px;">${escapeHtml(ev.operation)}</span>
                                <span style="font-size: 0.8rem; color: var(--text-main); font-weight: 500;">${escapeHtml(ev.details)}</span>
                            </div>
                            <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); white-space: nowrap;">${tStr}</span>
                        </div>
                    `;
                }).join('');
            }
        }
    }

    // Mark Current Task Completed
    async function completeCurrentTask() {
        if (!activeSimTask) {
            alert('No active task is currently in progress to complete.');
            return;
        }
        if (isSubmitting) return;
        isSubmitting = true;

        try {
            const res = await fetch(`/api/tasks/${activeSimTask.id}/complete`, { method: 'POST' });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                if (simStopwatchTimer) {
                    clearInterval(simStopwatchTimer);
                    simStopwatchTimer = null;
                }
                activeSimTask = null;
                refreshAll();
                fetchTaskHistory();
                fetchAnalytics();
            } else {
                alert(data.message || 'Error completing task.');
            }
        } catch (err) {
            console.error('Complete task error:', err);
        } finally {
            isSubmitting = false;
        }
    }

    // Cancel / Skip Task under Defined Policy
    async function cancelCurrentTask() {
        if (!activeSimTask) {
            alert('No active task is currently in progress to cancel.');
            return;
        }

        const reason = prompt('Please enter cancellation or skip reason:', 'Operator cancelled workload');
        if (!reason) return;

        if (isSubmitting) return;
        isSubmitting = true;

        try {
            const res = await fetch('/api/simulator/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: activeSimTask.id,
                    reason: reason.trim()
                })
            });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                if (simStopwatchTimer) {
                    clearInterval(simStopwatchTimer);
                    simStopwatchTimer = null;
                }
                activeSimTask = null;
                refreshAll();
                fetchTaskHistory();
                fetchAnalytics();
            } else {
                alert(data.message || 'Error cancelling task.');
            }
        } catch (err) {
            console.error('Cancel task error:', err);
        } finally {
            isSubmitting = false;
        }
    }

    // Wire Simulator Action Buttons
    document.getElementById('btn-sim-mark-completed')?.addEventListener('click', completeCurrentTask);
    document.getElementById('btn-card-mark-completed')?.addEventListener('click', completeCurrentTask);
    document.getElementById('btn-sim-cancel-task')?.addEventListener('click', cancelCurrentTask);
    document.getElementById('btn-card-cancel-task')?.addEventListener('click', cancelCurrentTask);
    document.getElementById('btn-sim-seed-samples')?.addEventListener('click', seedSampleTasks);
    document.getElementById('btn-sim-empty-seed')?.addEventListener('click', seedSampleTasks);
    document.getElementById('btn-sim-empty-create')?.addEventListener('click', openQuickAddModal);

    // Reset Queue / Simulator
    document.getElementById('btn-sim-reset')?.addEventListener('click', async () => {
        if (!confirm('Reset PriorityFlow to baseline initial demo state?')) return;
        try {
            const res = await fetch('/api/simulator/reset', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                if (simStopwatchTimer) {
                    clearInterval(simStopwatchTimer);
                    simStopwatchTimer = null;
                }
                activeSimTask = null;
                refreshAll();
                fetchTaskHistory();
            }
        } catch (err) {
            console.error('Reset error:', err);
        }
    });

    // Create Task Tab Presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.getAttribute('data-preset');
            const data = presets[key];
            if (!data) return;

            document.getElementById('task-title').value = data.title;
            document.getElementById('task-category').value = data.category;
            document.getElementById('task-duration').value = data.duration;
            document.getElementById('task-notes').value = data.notes;

            const radio = document.querySelector(`input[name="task-priority"][value="${data.priority}"]`);
            if (radio) radio.checked = true;
        });
    });

    // Create Task Tab Form Submit
    const formCreateTask = document.getElementById('create-task-form');
    const insertionResultCard = document.getElementById('insertion-result-card');

    if (formCreateTask) {
        formCreateTask.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (isSubmitting) return;

            const title = document.getElementById('task-title').value.trim();
            const category = document.getElementById('task-category').value;
            const selectedPrio = document.querySelector('input[name="task-priority"]:checked');
            const priority = parseInt(selectedPrio ? selectedPrio.value : 3);
            const description = document.getElementById('task-description').value.trim();
            const dueDate = document.getElementById('task-due-date').value;

            // Form validation
            if (!title || title.length < 2) {
                alert('Task title is required and must be at least 2 characters long.');
                document.getElementById('task-title').focus();
                return;
            }
            if (priority < 1 || priority > 4) {
                alert('Priority level must be between 1 (Critical) and 4 (Low).');
                return;
            }

            isSubmitting = true;

            const payload = {
                title: title,
                category: category,
                priority: priority,
                description: description,
                due_date: dueDate
            };

            try {
                const res = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (res.ok && data.status === 'success') {
                    // 1. Show the dynamic insertion result card and operation metrics
                    if (insertionResultCard) {
                        insertionResultCard.style.display = 'block';

                        // Fill metrics
                        const metrics = data.metrics || {};
                        const taskIdEl = document.getElementById('res-task-id');
                        const taskSeqEl = document.getElementById('res-task-seq');
                        const taskIndicesEl = document.getElementById('res-task-indices');
                        const taskCompsEl = document.getElementById('res-task-comparisons');
                        const taskSwapsEl = document.getElementById('res-task-swaps');

                        if (taskIdEl) taskIdEl.innerText = `#${metrics.task_id || data.task.id}`;
                        if (taskSeqEl) taskSeqEl.innerText = `#${metrics.insertion_sequence || data.task.insertion_sequence}`;
                        if (taskIndicesEl) taskIndicesEl.innerHTML = `[${metrics.initial_index}] &rarr; [${metrics.final_index}]`;
                        if (taskCompsEl) taskCompsEl.innerText = metrics.comparisons_count !== undefined ? metrics.comparisons_count : 0;
                        if (taskSwapsEl) taskSwapsEl.innerText = metrics.swaps_count !== undefined ? metrics.swaps_count : 0;

                        // Display clear explanation generated from the actual operation trace
                        const explanationEl = document.getElementById('res-task-explanation');
                        if (explanationEl) {
                            explanationEl.innerText = data.explanation || 'Task inserted into heap.';
                        }

                        // Display step-by-step trace timeline
                        const stepsContainer = document.getElementById('res-task-steps');
                        if (stepsContainer) {
                            const steps = data.steps || [];
                            if (steps.length === 0) {
                                stepsContainer.innerHTML = '<div class="swap-step-row" style="color: var(--text-muted);">Root position (Index 0). Min-heap invariant satisfied immediately.</div>';
                            } else {
                                stepsContainer.innerHTML = steps.map(s => {
                                    if (s.action === 'swap') {
                                        return `<div class="swap-step-row" style="color: var(--brand-indigo); font-weight: 600;">
                                            &bull; <strong>Swap:</strong> Swapped child at [${s.index_a}] upward with parent at [${s.index_b}] (${s.reason || 'Restoring min-heap invariant'})
                                        </div>`;
                                    } else if (s.action === 'compare') {
                                        const swapStatus = s.swap_needed 
                                            ? '<span style="color: #ef4444; font-weight: 600;">[Child Urgency > Parent &rarr; Swap Upward]</span>' 
                                            : '<span style="color: #10b981; font-weight: 600;">[Invariant Satisfied &rarr; Sift Terminated]</span>';
                                        return `<div class="swap-step-row" style="color: var(--text-secondary);">
                                            &bull; <strong>Comparison:</strong> Child at index ${s.child_index} (P${s.child_priority}) vs Parent at index ${s.parent_index} (P${s.parent_priority}) &rarr; ${swapStatus}
                                        </div>`;
                                    } else {
                                        return `<div class="swap-step-row">${s.reason || s.action}</div>`;
                                    }
                                }).join('');
                            }
                        }

                        // Scroll smoothly to the result card
                        insertionResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }

                    // 2. Fetch fresh heap state for final snapshot and logical order
                    const heapRes = await fetch('/api/heap/state');
                    const heapData = await heapRes.json();
                    const finalHeap = heapData.array || [];
                    const initialSnapshot = JSON.parse(JSON.stringify(currentHeapArray));
                    currentHeapArray = finalHeap;

                    // 3. Load real insertion trace into the interactive visualizer animation engine
                    visualizer.loadTrace(
                        data.steps || [],
                        initialSnapshot,
                        finalHeap,
                        'insert',
                        heapData.logical_order || []
                    );

                    // 4. Update dashboard statistics, workers, and task history immediately
                    fetchOverview();
                    fetchWorkers();
                    fetchTaskHistory();
                } else {
                    alert(data.message || 'Failed to enqueue task');
                }
            } catch (err) {
                console.error(err);
                alert('Network error while creating task.');
            } finally {
                isSubmitting = false;
            }
        });
    }

    // Action buttons inside the insertion result card
    document.getElementById('btn-res-view-tree')?.addEventListener('click', () => {
        switchSection('section-live-queue');
    });

    document.getElementById('btn-res-add-another')?.addEventListener('click', () => {
        if (formCreateTask) formCreateTask.reset();
        if (insertionResultCard) insertionResultCard.style.display = 'none';
        document.getElementById('task-title')?.focus();
    });

    // Task History Filters & Export
    document.getElementById('table-search-input')?.addEventListener('input', fetchTaskHistory);
    document.getElementById('table-status-filter')?.addEventListener('change', fetchTaskHistory);
    document.getElementById('table-category-filter')?.addEventListener('change', fetchTaskHistory);
    document.getElementById('btn-export-json')?.addEventListener('click', () => {
        window.location.href = '/api/tasks/export';
    });

    // Priority Tuning Modal
    const modalPriority = document.getElementById('modal-update-priority');
    const btnCloseModal = document.getElementById('btn-close-priority-modal');
    const btnCancelModal = document.getElementById('btn-cancel-priority-modal');
    const btnConfirmModal = document.getElementById('btn-confirm-priority-update');

    window.openPriorityModal = (taskId, taskTitle, currentPriority) => {
        document.getElementById('modal-task-id').value = taskId;
        document.getElementById('modal-task-title-text').innerText = `Re-prioritizing: ${taskTitle} (Current: P${currentPriority})`;
        document.getElementById('modal-new-priority-select').value = currentPriority;
        if (modalPriority) modalPriority.classList.remove('hidden');
    };

    if (btnCloseModal) btnCloseModal.addEventListener('click', () => modalPriority.classList.add('hidden'));
    if (btnCancelModal) btnCancelModal.addEventListener('click', () => modalPriority.classList.add('hidden'));

    if (btnConfirmModal) {
        btnConfirmModal.addEventListener('click', async () => {
            const taskId = document.getElementById('modal-task-id').value;
            const newPrio = parseInt(document.getElementById('modal-new-priority-select').value);

            try {
                const res = await fetch(`/api/tasks/${taskId}/update-priority`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ priority: newPrio })
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    modalPriority.classList.add('hidden');
                    refreshAll();
                    fetchTaskHistory();
                } else {
                    alert(data.message || 'Failed to update priority');
                }
            } catch (err) {
                console.error(err);
            }
        });
    }

    // Complete Task Action
    window.completeTask = async (taskId) => {
        try {
            const res = await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                refreshAll();
                fetchTaskHistory();
            }
        } catch (err) {
            console.error(err);
        }
    };

    // Delete / Cancel Task Action
    window.deleteTask = async (taskId) => {
        if (!confirm('Delete/Cancel this task from the priority queue?')) return;
        try {
            const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.status === 'success') {
                refreshAll();
                fetchTaskHistory();
            }
        } catch (err) {
            console.error(err);
        }
    };

    // About Project: Python heapq Verification
    document.getElementById('btn-run-about-verify')?.addEventListener('click', async () => {
        const outBox = document.getElementById('about-heapq-output');
        if (!outBox) return;
        outBox.innerHTML = '<span style="color: #60a5fa;">Executing side-by-side verification with Python heapq...</span>';

        try {
            const res = await fetch('/api/dsa/verify-heapq');
            const data = await res.json();

            if (data.status === 'success') {
                const badge = data.identical 
                    ? '<span style="color: #10b981; font-weight: 700;">[PASSED &bull; 100% IDENTICAL EXTRACTION SEQUENCE]</span>' 
                    : '<span style="color: #ef4444; font-weight: 700;">[FAIL &bull; MISMATCH]</span>';

                let orderStr = data.custom_heap_order.map((t, idx) => 
                    `#${idx + 1}: ${t.title} (P${t.priority})`
                ).join(' &rarr; ');

                outBox.innerHTML = `
                    <div style="margin-bottom: 8px;">${badge}</div>
                    <div style="font-size: 0.72rem; line-height: 1.6;">
                        <strong>Extraction Sequence:</strong><br>
                        ${orderStr || 'Queue is currently empty.'}<br><br>
                        <em>${data.explanation}</em>
                    </div>
                `;
            }
        } catch (err) {
            outBox.innerHTML = '<span style="color: #ef4444;">Verification call failed.</span>';
        }
    });

    // Fit Tree View Button
    document.getElementById('btn-fit-tree-view')?.addEventListener('click', () => {
        if (currentHeapArray.length > 0) {
            visualizer.renderTree(currentHeapArray);
        }
    });

    // Close modals on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) backdrop.classList.add('hidden');
        });
    });

    // ---------------------------------------------------------
    // Initial Load & Real-Time Sync Heartbeat
    // ---------------------------------------------------------
    refreshAll();
    fetchTaskHistory();
    // Periodic polling every 3.5s to ensure all statistics remain in sync across tabs
    setInterval(refreshAll, 3500);
});
