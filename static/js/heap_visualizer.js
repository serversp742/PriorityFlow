/**
 * PriorityFlow - Interactive Dynamic SVG Binary Tree & Array Visualizer
 * ======================================================================
 * Features:
 * 1. Computes dynamic (x, y) coordinates for binary tree levels.
 * 2. Draws SVG edges with branch formulas (L: 2i+1, R: 2i+2).
 * 3. Every node displays:
 *    - Task ID (#<id>)
 *    - Task Title
 *    - Priority Number (P1, P2, P3, P4)
 *    - Priority Label (Critical, High, Medium, Low)
 *    - Heap Index ([0], [1], ...)
 *    - Insertion Sequence (Seq #<seq>)
 * 4. Dual comparative panels:
 *    - Internal contiguous RAM buffer heap[] (partially ordered)
 *    - Logical execution order (separate non-mutating view of eligible tasks)
 * 5. Full step-by-step & automatic playback animation engine:
 *    - Insertion sift-up animation
 *    - Extraction sift-down animation
 *    - Uses real backend operation traces and actual snapshots
 * 6. Controls: Play, Pause, Step-by-Step, Next Step, Reset, Speed, Recenter.
 */

class HeapVisualizer {
    constructor(svgElementId, arrayStripElementId, traceContainerId, logicalOrderId = 'logical-order-list') {
        this.svg = document.getElementById(svgElementId);
        this.arrayStrip = document.getElementById(arrayStripElementId);
        this.traceContainer = document.getElementById(traceContainerId);
        this.logicalOrderContainer = document.getElementById(logicalOrderId);

        // UI Badges & Controls
        this.narrationBanner = document.getElementById('anim-narration-banner');
        this.narrationText = document.getElementById('anim-narration-text');
        this.narrationTag = document.getElementById('anim-narration-tag');
        this.narrationStatus = document.getElementById('anim-narration-status');
        this.stepCounterBadge = document.getElementById('anim-step-counter');
        this.stepModeStatus = document.getElementById('anim-step-mode-status');
        this.speedSelect = document.getElementById('select-anim-speed');
        this.invariantBadge = document.getElementById('heap-invariant-badge');
        this.logicalCountBadge = document.getElementById('logical-order-count');

        // Layout parameters
        this.nodeWidth = 132;
        this.nodeHeight = 72;
        this.levelHeight = 110;
        this.marginTop = 54;

        // Current stable data
        this.currentNodes = [];
        this.logicalOrder = [];

        // Animation Engine State
        this.animSteps = [];
        this.animWorkingNodes = [];
        this.animFinalNodes = [];
        this.currentStepIdx = 0;
        this.isPlaying = false;
        this.isStepMode = false;
        this.animSpeed = 1.0;
        this.animTimer = null;
        this.baseDelay = 1100;

        window.addEventListener('resize', () => {
            if (this.currentNodes.length > 0) {
                this.renderTree(this.animWorkingNodes.length > 0 ? this.animWorkingNodes : this.currentNodes);
            }
        });

        this.initControls();
    }

    initControls() {
        const btnPlay = document.getElementById('btn-anim-play');
        const btnPause = document.getElementById('btn-anim-pause');
        const btnStepMode = document.getElementById('btn-anim-step-mode');
        const btnNext = document.getElementById('btn-anim-next');
        const btnReset = document.getElementById('btn-anim-reset');

        btnPlay?.addEventListener('click', () => this.play());
        btnPause?.addEventListener('click', () => this.pause());
        btnStepMode?.addEventListener('click', () => this.toggleStepMode());
        btnNext?.addEventListener('click', () => this.nextStep());
        btnReset?.addEventListener('click', () => this.resetVisualization());

        this.speedSelect?.addEventListener('change', (e) => {
            this.animSpeed = parseFloat(e.target.value) || 1.0;
        });

        document.getElementById('btn-fit-tree-view')?.addEventListener('click', () => {
            this.renderTree(this.animWorkingNodes.length > 0 ? this.animWorkingNodes : this.currentNodes);
        });
    }

    /**
     * Updates stable heap state from backend /api/heap/state.
     */
    update(heapArray, lastSteps = [], logicalOrder = []) {
        this.currentNodes = heapArray || [];
        this.logicalOrder = logicalOrder || [];

        // If not actively animating, refresh working view
        if (!this.isPlaying && this.animSteps.length === 0) {
            this.animWorkingNodes = JSON.parse(JSON.stringify(this.currentNodes));
            this.renderTree(this.currentNodes);
            this.renderArrayStrip(this.currentNodes);
            this.renderTraceSteps(lastSteps);
            this.renderLogicalOrder(this.logicalOrder);
            this.updateNarration('IDLE', 'Heap invariant satisfied. Root task has highest SLA priority.', 'idle');
            this.updateStepBadge(0, 0);
        }
    }

    /**
     * Loads an authoritative backend trace sequence (insertion or extraction)
     * and sets up the animation timeline.
     */
    loadTrace(steps, initialSnapshot, finalSnapshot, opType = 'general', logicalOrder = null) {
        this.pause();
        this.animSteps = steps || [];
        this.animWorkingNodes = JSON.parse(JSON.stringify(initialSnapshot || []));
        this.animFinalNodes = JSON.parse(JSON.stringify(finalSnapshot || []));
        this.currentStepIdx = 0;
        if (logicalOrder) {
            this.logicalOrder = logicalOrder;
            this.renderLogicalOrder(logicalOrder);
        }

        this.renderTree(this.animWorkingNodes);
        this.renderArrayStrip(this.animWorkingNodes);
        this.renderTraceSteps(this.animSteps);
        this.updateStepBadge(0, this.animSteps.length);

        const opTitle = opType === 'insert' ? 'INSERTION SIFT-UP' : (opType === 'extract' ? 'EXTRACTION SIFT-DOWN' : 'OPERATION TRACE');
        this.updateNarration(opTitle, `Loaded ${this.animSteps.length} trace step(s). Click "Play Animation" or "Next Step".`, 'comparing');

        if (!this.isStepMode) {
            this.play();
        }
    }

    play() {
        if (this.animSteps.length === 0) {
            this.updateNarration('STATUS', 'No active operation trace to play. Add a task or execute the next task to trace.', 'idle');
            return;
        }

        if (this.currentStepIdx >= this.animSteps.length) {
            // Replay from beginning
            this.currentStepIdx = 0;
            this.animWorkingNodes = JSON.parse(JSON.stringify(this.currentNodes));
        }

        this.isPlaying = true;
        this.isStepMode = false;
        this.updateStepModeUI();
        this.runNextStep();
    }

    pause() {
        this.isPlaying = false;
        if (this.animTimer) {
            clearTimeout(this.animTimer);
            this.animTimer = null;
        }
        this.updateNarration('PAUSED', 'Animation paused. Click "Play Animation" to resume or "Next Step" to advance manually.', 'idle');
    }

    toggleStepMode() {
        this.isStepMode = !this.isStepMode;
        if (this.isStepMode && this.isPlaying) {
            this.pause();
        }
        this.updateStepModeUI();
    }

    updateStepModeUI() {
        if (this.stepModeStatus) {
            this.stepModeStatus.innerText = this.isStepMode ? 'ON' : 'OFF';
            this.stepModeStatus.style.color = this.isStepMode ? '#10b981' : 'var(--text-muted)';
        }
        const btnStep = document.getElementById('btn-anim-step-mode');
        if (btnStep) {
            btnStep.className = this.isStepMode ? 'btn btn-secondary btn-sm' : 'btn btn-outline btn-sm';
        }
    }

    nextStep() {
        if (this.animSteps.length === 0) return;
        if (this.isPlaying) this.pause();
        this.executeCurrentStep();
    }

    resetVisualization() {
        this.pause();
        this.animSteps = [];
        this.currentStepIdx = 0;
        this.animWorkingNodes = JSON.parse(JSON.stringify(this.currentNodes));
        this.renderTree(this.currentNodes);
        this.renderArrayStrip(this.currentNodes);
        this.renderLogicalOrder(this.logicalOrder);
        this.clearHighlights();
        this.updateNarration('RESET', 'Visualization restored to current backend heap state. Min-heap invariant verified.', 'root');
        this.updateStepBadge(0, 0);
    }

    runNextStep() {
        if (!this.isPlaying) return;

        if (this.currentStepIdx >= this.animSteps.length) {
            this.finishAnimation();
            return;
        }

        this.executeCurrentStep();

        if (this.isPlaying && this.currentStepIdx < this.animSteps.length) {
            const delay = Math.max(300, this.baseDelay / this.animSpeed);
            this.animTimer = setTimeout(() => this.runNextStep(), delay);
        } else if (this.currentStepIdx >= this.animSteps.length) {
            const delay = Math.max(400, this.baseDelay / this.animSpeed);
            this.animTimer = setTimeout(() => this.finishAnimation(), delay);
        }
    }

    /**
     * Executes a single algorithmic trace step from backend.
     */
    executeCurrentStep() {
        if (this.currentStepIdx >= this.animSteps.length) return;

        const step = this.animSteps[this.currentStepIdx];
        this.currentStepIdx++;
        this.updateStepBadge(this.currentStepIdx, this.animSteps.length);

        this.clearHighlights();

        switch (step.action) {
            case 'insert': {
                // Task added at end of heap
                const idx = step.index;
                const taskTitle = step.task;
                const prio = step.priority;
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: APPEND AT END`,
                    `Appended new task "${taskTitle}" (P${prio}) at array index [${idx}]. Initiating sift-up traversal.`,
                    'comparing'
                );
                this.renderTree(this.animWorkingNodes);
                this.renderArrayStrip(this.animWorkingNodes);
                this.highlightNode(idx, 'highlight-new-node');
                break;
            }

            case 'compare': {
                // Sift-up comparison: Child at child_index vs Parent at parent_index
                const cIdx = step.child_index;
                const pIdx = step.parent_index;
                const cPrio = step.child_priority;
                const pPrio = step.parent_priority;
                const swapNeeded = step.swap_needed;

                let msg = `Compared Child [${cIdx}] (P${cPrio}) with Parent [${pIdx}] (P${pPrio}). `;
                if (swapNeeded) {
                    msg += `Child has higher SLA priority (smaller key) than Parent. Swap required upward.`;
                } else {
                    msg += `Parent priority <= Child priority. Min-heap invariant satisfied; no swap needed.`;
                }

                this.updateNarration(`STEP ${this.currentStepIdx}: COMPARE PARENT & CHILD`, msg, 'comparing');
                this.highlightNode(cIdx, 'highlight-comparing');
                this.highlightNode(pIdx, 'highlight-comparing');
                this.highlightEdge(pIdx, cIdx, 'edge-active');
                break;
            }

            case 'swap': {
                // Swap elements between index_a and index_b
                const idxA = step.index_a;
                const idxB = step.index_b;

                // Swap in working array if both exist
                if (idxA < this.animWorkingNodes.length && idxB < this.animWorkingNodes.length) {
                    const temp = this.animWorkingNodes[idxA];
                    this.animWorkingNodes[idxA] = this.animWorkingNodes[idxB];
                    this.animWorkingNodes[idxB] = temp;
                }

                this.updateNarration(
                    `STEP ${this.currentStepIdx}: SWAP EXECUTED`,
                    `Swapped [${idxA}] "${step.task_a}" with [${idxB}] "${step.task_b}". ${step.reason || ''}`,
                    'swapping'
                );

                this.renderTree(this.animWorkingNodes);
                this.renderArrayStrip(this.animWorkingNodes);
                this.highlightNode(idxA, 'highlight-swapping');
                this.highlightNode(idxB, 'highlight-swapping');
                this.highlightEdge(Math.min(idxA, idxB), Math.max(idxA, idxB), 'edge-swapped');
                break;
            }

            case 'sift_up_complete': {
                const finalIdx = step.final_index;
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: SIFT-UP COMPLETE`,
                    `Task settled at heap index [${finalIdx}]. ${step.is_root ? 'Promoted to Root (highest priority).' : ''} Min-heap invariant restored.`,
                    'root'
                );
                this.renderTree(this.animWorkingNodes);
                this.renderArrayStrip(this.animWorkingNodes);
                this.highlightNode(finalIdx, 'highlight-final-root');
                break;
            }

            case 'extract_start': {
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: IDENTIFY NEXT ELIGIBLE TASK`,
                    `Root task #${step.task_id} "${step.task}" (P${step.priority}, Seq #${step.insertion_sequence}) selected for execution.`,
                    'root'
                );
                this.highlightNode(0, 'highlight-comparing');
                break;
            }

            case 'remove_root': {
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: REMOVE ROOT`,
                    `Removed root task #${step.task_id} "${step.task}" from index [0]. Preparing to replace root with last element.`,
                    'comparing'
                );
                this.highlightNode(0, 'highlight-extracted');
                break;
            }

            case 'replace_root': {
                // Last element moved to root in working snapshot
                if (this.animWorkingNodes.length > 1) {
                    const lastEl = this.animWorkingNodes.pop();
                    this.animWorkingNodes[0] = lastEl;
                } else {
                    this.animWorkingNodes = [];
                }

                this.updateNarration(
                    `STEP ${this.currentStepIdx}: MOVE LAST ELEMENT TO ROOT`,
                    `Moved last array leaf (Task #${step.task_id} "${step.task}") to root index [0]. Initiating sift-down traversal.`,
                    'swapping'
                );
                this.renderTree(this.animWorkingNodes);
                this.renderArrayStrip(this.animWorkingNodes);
                if (this.animWorkingNodes.length > 0) {
                    this.highlightNode(0, 'highlight-swapping');
                }
                break;
            }

            case 'compare_children': {
                const lIdx = step.left_index;
                const rIdx = step.right_index;
                const chosenIdx = step.selected_child_index;
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: COMPARE SIBLING CHILDREN`,
                    step.reason || `Compared Left [${lIdx}] vs Right [${rIdx}]. Selected Child [${chosenIdx}] with smaller scheduling key.`,
                    'comparing'
                );
                this.highlightNode(lIdx, 'highlight-comparing');
                if (rIdx < this.animWorkingNodes.length) {
                    this.highlightNode(rIdx, 'highlight-comparing');
                }
                break;
            }

            case 'compare_parent_child': {
                const pIdx = step.parent_index;
                const cIdx = step.child_index;
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: COMPARE ROOT/PARENT WITH CHILD`,
                    step.reason || `Compared Parent [${pIdx}] with Child [${cIdx}]. ${step.swap_needed ? 'Swap required downward.' : 'Invariant satisfied.'}`,
                    'comparing'
                );
                this.highlightNode(pIdx, 'highlight-comparing');
                this.highlightNode(cIdx, 'highlight-comparing');
                this.highlightEdge(pIdx, cIdx, 'edge-active');
                break;
            }

            case 'sift_down_complete': {
                this.updateNarration(
                    `STEP ${this.currentStepIdx}: SIFT-DOWN COMPLETE`,
                    step.reason || `Sift-down complete. Root is now highest priority task. Min-heap invariant restored.`,
                    'root'
                );
                if (this.animWorkingNodes.length > 0) {
                    this.highlightNode(0, 'highlight-final-root');
                }
                break;
            }

            case 'queue_now_empty': {
                this.animWorkingNodes = [];
                this.renderTree([]);
                this.renderArrayStrip([]);
                this.updateNarration('QUEUE EMPTY', 'Extracted the last remaining task. Priority queue is now empty.', 'idle');
                break;
            }

            default: {
                this.updateNarration(`STEP ${this.currentStepIdx}: ${step.action}`, step.reason || '', 'comparing');
                break;
            }
        }
    }

    finishAnimation() {
        this.isPlaying = false;
        if (this.animTimer) {
            clearTimeout(this.animTimer);
            this.animTimer = null;
        }

        // Display final authoritative heap matching backend actual array
        if (this.animFinalNodes.length > 0) {
            this.animWorkingNodes = JSON.parse(JSON.stringify(this.animFinalNodes));
            this.currentNodes = JSON.parse(JSON.stringify(this.animFinalNodes));
        }

        this.renderTree(this.animWorkingNodes);
        this.renderArrayStrip(this.animWorkingNodes);
        this.renderLogicalOrder(this.logicalOrder);
        this.clearHighlights();

        if (this.animWorkingNodes.length > 0) {
            this.highlightNode(0, 'highlight-final-root');
            this.updateNarration(
                'ANIMATION FINISHED',
                `All operations successfully executed. Final heap structure matches backend array. Root [0] is "${this.animWorkingNodes[0].title}" (P${this.animWorkingNodes[0].priority}).`,
                'root'
            );
        } else {
            this.updateNarration('ANIMATION FINISHED', 'Operation complete. Priority queue is now empty.', 'idle');
        }
    }

    updateNarration(tag, message, state = 'idle') {
        if (this.narrationTag) this.narrationTag.innerText = tag;
        if (this.narrationText) this.narrationText.innerText = message;
        if (this.narrationStatus) {
            this.narrationStatus.innerText = state === 'idle' ? 'Invariant Verified' : (state === 'root' ? 'Invariant Restored' : 'Traversing...');
        }
        if (this.narrationBanner) {
            this.narrationBanner.className = 'anim-narration-banner';
            if (state === 'comparing') this.narrationBanner.classList.add('active-comparing');
            else if (state === 'swapping') this.narrationBanner.classList.add('active-swapping');
            else if (state === 'root') this.narrationBanner.classList.add('active-root');
        }
    }

    updateStepBadge(current, total) {
        if (this.stepCounterBadge) {
            this.stepCounterBadge.innerText = total > 0 ? `Step: ${current} / ${total}` : 'Step: 0 / 0';
        }
    }

    // -------------------------------------------------------------
    // Tree Coordinates & SVG Generation
    // -------------------------------------------------------------

    computeNodeCoordinates(nodes, width) {
        const coords = [];
        const n = nodes.length;

        for (let i = 0; i < n; i++) {
            const depth = Math.floor(Math.log2(i + 1));
            const levelStartIndex = Math.pow(2, depth) - 1;
            const indexInLevel = i - levelStartIndex;
            const maxNodesInLevel = Math.pow(2, depth);

            const segmentWidth = width / (maxNodesInLevel + 1);
            const x = segmentWidth * (indexInLevel + 1);
            const y = this.marginTop + depth * this.levelHeight;

            coords.push({ ...nodes[i], x, y, depth });
        }
        return coords;
    }

    renderTree(nodes) {
        if (!this.svg) return;

        const emptyAlert = document.getElementById('tree-empty-alert');
        if (!nodes || nodes.length === 0) {
            this.svg.innerHTML = '';
            if (emptyAlert) emptyAlert.style.display = 'block';
            return;
        }
        if (emptyAlert) emptyAlert.style.display = 'none';

        const maxDepth = Math.floor(Math.log2(nodes.length));
        const neededWidth = Math.max(760, Math.pow(2, maxDepth) * 145);
        this.svg.style.minWidth = `${neededWidth}px`;

        const neededHeight = Math.max(420, this.marginTop + (maxDepth + 1) * this.levelHeight + 50);
        this.svg.setAttribute('height', neededHeight);

        const positionedNodes = this.computeNodeCoordinates(nodes, neededWidth);

        let svgHtml = '';

        // 1. Draw connecting edges with formula labels (L: 2i+1, R: 2i+2)
        for (let i = 0; i < positionedNodes.length; i++) {
            const parent = positionedNodes[i];
            const leftIdx = 2 * i + 1;
            const rightIdx = 2 * i + 2;

            if (leftIdx < positionedNodes.length) {
                const leftChild = positionedNodes[leftIdx];
                svgHtml += this.createEdge(parent, leftChild, 'L: 2i+1', i, leftIdx);
            }

            if (rightIdx < positionedNodes.length) {
                const rightChild = positionedNodes[rightIdx];
                svgHtml += this.createEdge(parent, rightChild, 'R: 2i+2', i, rightIdx);
            }
        }

        // 2. Draw Nodes displaying all 6 mandatory attributes
        for (let i = 0; i < positionedNodes.length; i++) {
            svgHtml += this.createNode(positionedNodes[i], i);
        }

        this.svg.innerHTML = svgHtml;
        this.attachNodeListeners();
    }

    createEdge(parent, child, label, pIdx, cIdx) {
        const edgeId = `edge-${pIdx}-${cIdx}`;
        // Connect from bottom center of parent to top center of child card
        const startX = parent.x;
        const startY = parent.y + (this.nodeHeight / 2);
        const endX = child.x;
        const endY = child.y - (this.nodeHeight / 2);

        const midX = (startX + endX) / 2;
        const midY = (startY + endY) / 2;

        return `
            <g class="heap-edge-group" id="${edgeId}">
                <line class="heap-edge" id="line-${pIdx}-${cIdx}" x1="${startX}" y1="${startY}" x2="${endX}" y2="${endY}" />
                <rect class="edge-label-box" x="${midX - 22}" y="${midY - 8}" width="44" height="16" />
                <text class="edge-label" x="${midX}" y="${midY + 1}">${label}</text>
            </g>
        `;
    }

    /**
     * Renders an individual tree node card containing all 6 required attributes:
     * 1. Task ID
     * 2. Task Title
     * 3. Priority Number
     * 4. Priority Label
     * 5. Heap Index
     * 6. Insertion Sequence
     */
    createNode(node, index) {
        const isRoot = index === 0 ? 'is-root' : '';
        const priority = node.priority || 3;
        const priorityLabel = node.priority_label || this.getPriorityLabel(priority);
        const taskId = node.task_id || index;
        const seq = node.insertion_sequence !== undefined ? node.insertion_sequence : 0;
        const rawTitle = node.title || `Task #${taskId}`;
        const titleSnippet = rawTitle.length > 15 ? rawTitle.substring(0, 13) + '..' : rawTitle;

        // Card geometry centered around (node.x, node.y)
        const halfW = this.nodeWidth / 2;
        const halfH = this.nodeHeight / 2;
        const cardX = -halfW;
        const cardY = -halfH;

        // Priority-specific accent color
        let prioColor = '#3b82f6';
        if (priority === 1) prioColor = '#ef4444';
        else if (priority === 2) prioColor = '#f97316';
        else if (priority === 3) prioColor = '#f59e0b';

        return `
            <g class="heap-node-group ${isRoot}" id="tree-node-${index}" data-index="${index}" transform="translate(${node.x}, ${node.y})">
                <!-- Card Background -->
                <rect class="node-card-bg node-bg-p${priority}" x="${cardX}" y="${cardY}" width="${this.nodeWidth}" height="${this.nodeHeight}" />

                <!-- Top Row: Priority Pill & Heap Index Badge -->
                <rect x="${cardX + 8}" y="${cardY + 8}" width="68" height="15" rx="3" fill="${prioColor}" fill-opacity="0.12" />
                <text class="node-prio-text" x="${cardX + 12}" y="${cardY + 19}" fill="${prioColor}">P${priority} &bull; ${priorityLabel}</text>
                
                <text class="node-idx-badge-text" x="${halfW - 10}" y="${cardY + 19}" text-anchor="end">[${index}]</text>

                <!-- Middle Row: Task Title -->
                <text class="node-title-text" x="0" y="${cardY + 41}" text-anchor="middle" title="${rawTitle}">${titleSnippet}</text>

                <!-- Bottom Row: Task ID & Persistent Insertion Sequence -->
                <text class="node-sub-text" x="${cardX + 10}" y="${cardY + 61}" text-anchor="start">#${taskId}</text>
                <text class="node-sub-text" x="${halfW - 10}" y="${cardY + 61}" text-anchor="end">Seq #${seq}</text>
            </g>
        `;
    }

    getPriorityLabel(p) {
        const labels = { 1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low' };
        return labels[p] || `P${p}`;
    }

    // -------------------------------------------------------------
    // Highlights & Interactions
    // -------------------------------------------------------------

    highlightNode(index, className) {
        const nodeEl = document.getElementById(`tree-node-${index}`);
        if (nodeEl) nodeEl.classList.add(className);

        const arrayCell = document.getElementById(`array-cell-${index}`);
        if (arrayCell) {
            arrayCell.classList.add('active-hover');
            arrayCell.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        }
    }

    highlightEdge(parentIdx, childIdx, className) {
        const edgeLine = document.getElementById(`line-${parentIdx}-${childIdx}`);
        if (edgeLine) edgeLine.classList.add(className);
    }

    clearHighlights() {
        const highlightedNodes = this.svg?.querySelectorAll(
            '.highlight-comparing, .highlight-swapping, .highlight-final-root, .highlight-new-node, .highlight-extracted'
        );
        highlightedNodes?.forEach(el => {
            el.classList.remove(
                'highlight-comparing', 'highlight-swapping', 'highlight-final-root', 'highlight-new-node', 'highlight-extracted'
            );
        });

        const highlightedEdges = this.svg?.querySelectorAll('.edge-active, .edge-swapped');
        highlightedEdges?.forEach(el => el.classList.remove('edge-active', 'edge-swapped'));

        const activeCells = document.querySelectorAll('.array-cell.active-hover');
        activeCells.forEach(el => el.classList.remove('active-hover'));
    }

    attachNodeListeners() {
        const groups = this.svg.querySelectorAll('.heap-node-group');
        groups.forEach(group => {
            const index = parseInt(group.getAttribute('data-index'));

            group.addEventListener('mouseenter', () => this.highlightNodeRelations(index));
            group.addEventListener('mouseleave', () => this.clearRelationHover());
            group.addEventListener('click', () => {
                const nodeData = (this.animWorkingNodes.length > 0 ? this.animWorkingNodes : this.currentNodes)[index];
                if (nodeData && window.openPriorityModal) {
                    window.openPriorityModal(nodeData.task_id, nodeData.title, nodeData.priority);
                }
            });
        });
    }

    highlightNodeRelations(index) {
        const nodes = this.animWorkingNodes.length > 0 ? this.animWorkingNodes : this.currentNodes;
        if (!nodes || index >= nodes.length) return;

        const parentIdx = Math.floor((index - 1) / 2);
        const leftIdx = 2 * index + 1;
        const rightIdx = 2 * index + 2;

        const detailsEl = document.getElementById('hover-node-math-details');
        const node = nodes[index];

        if (detailsEl && node) {
            const parentText = index > 0 ? `Parent: [${parentIdx}] (P${nodes[parentIdx]?.priority})` : 'Parent: None (Root Element)';
            const leftText = leftIdx < nodes.length ? `Left: [${leftIdx}] (P${nodes[leftIdx]?.priority})` : 'Left: None';
            const rightText = rightIdx < nodes.length ? `Right: [${rightIdx}] (P${nodes[rightIdx]?.priority})` : 'Right: None';

            detailsEl.innerHTML = `<strong>Selected Node [${index}] ${node.title} (P${node.priority})</strong> &bull; ${parentText} &bull; ${leftText} &bull; ${rightText}`;
        }

        // Highlight selected node and relations in tree
        const activeNode = document.getElementById(`tree-node-${index}`);
        if (activeNode) activeNode.classList.add('highlight-comparing');

        if (index > 0) {
            const pNode = document.getElementById(`tree-node-${parentIdx}`);
            if (pNode) pNode.classList.add('highlight-new-node');
            this.highlightEdge(parentIdx, index, 'edge-active');
        }

        if (leftIdx < nodes.length) {
            const lNode = document.getElementById(`tree-node-${leftIdx}`);
            if (lNode) lNode.classList.add('highlight-new-node');
            this.highlightEdge(index, leftIdx, 'edge-active');
        }

        if (rightIdx < nodes.length) {
            const rNode = document.getElementById(`tree-node-${rightIdx}`);
            if (rNode) rNode.classList.add('highlight-new-node');
            this.highlightEdge(index, rightIdx, 'edge-active');
        }

        const arrayCell = document.getElementById(`array-cell-${index}`);
        if (arrayCell) {
            arrayCell.classList.add('active-hover');
            arrayCell.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        }
    }

    clearRelationHover() {
        if (!this.isPlaying) {
            this.clearHighlights();
            const detailsEl = document.getElementById('hover-node-math-details');
            if (detailsEl) {
                detailsEl.innerText = 'Hover an array index to inspect parent/child relations';
            }
        }
    }

    // -------------------------------------------------------------
    // Dual Comparative Panels: Array & Logical Execution Order
    // -------------------------------------------------------------

    renderArrayStrip(nodes) {
        if (!this.arrayStrip) return;

        if (!nodes || nodes.length === 0) {
            this.arrayStrip.innerHTML = '<span style="font-size: 0.8rem; color: var(--text-muted); padding: 10px;">Internal memory buffer empty.</span>';
            return;
        }

        let html = '';
        for (let i = 0; i < nodes.length; i++) {
            const node = nodes[i];
            const isRoot = i === 0 ? 'is-root' : '';
            const parent = i > 0 ? Math.floor((i - 1) / 2) : '-';
            const left = (2 * i + 1 < nodes.length) ? (2 * i + 1) : '-';
            const right = (2 * i + 2 < nodes.length) ? (2 * i + 2) : '-';
            const pLabel = node.priority_label || this.getPriorityLabel(node.priority);

            html += `
                <div class="array-cell ${isRoot}" id="array-cell-${i}" data-index="${i}">
                    <div class="array-cell-header">
                        <span class="array-idx-badge">[${i}]</span>
                        <span class="badge badge-p${node.priority}">P${node.priority} ${pLabel}</span>
                    </div>
                    <div class="array-cell-title" title="${node.title}">${node.title}</div>
                    <div class="array-cell-meta">#${node.task_id} &bull; Seq #${node.insertion_sequence || 0}</div>
                    <div class="array-cell-pointers">
                        <span>P: ${parent}</span>
                        <span>L: ${left}</span>
                        <span>R: ${right}</span>
                    </div>
                </div>
            `;
        }

        this.arrayStrip.innerHTML = html;

        const cells = this.arrayStrip.querySelectorAll('.array-cell');
        cells.forEach(cell => {
            const idx = parseInt(cell.getAttribute('data-index'));
            cell.addEventListener('mouseenter', () => this.highlightNodeRelations(idx));
            cell.addEventListener('mouseleave', () => this.clearRelationHover());
            cell.addEventListener('click', () => {
                const nodeData = nodes[idx];
                if (nodeData && window.openPriorityModal) {
                    window.openPriorityModal(nodeData.task_id, nodeData.title, nodeData.priority);
                }
            });
        });
    }

    /**
     * Renders the second comparative panel showing the Logical Execution Order.
     * Calculated using a separate non-mutating view of eligible tasks.
     * Does not mutate the real heap array.
     */
    renderLogicalOrder(logicalTasks) {
        if (!this.logicalOrderContainer) return;

        const tasks = logicalTasks || [];
        if (this.logicalCountBadge) {
            this.logicalCountBadge.innerText = `${tasks.length} Eligible Tasks`;
        }

        if (tasks.length === 0) {
            this.logicalOrderContainer.innerHTML = `
                <div class="empty-state-box" style="padding: 16px; font-size: 0.8rem;">
                    No pending tasks in queue. All workloads completed or queue is empty.
                </div>
            `;
            return;
        }

        let html = '';
        tasks.forEach((t, idx) => {
            const isNext = idx === 0;
            const rankLabel = isNext ? '#1 NEXT TO DISPATCH' : `#${idx + 1}`;
            const prioLabel = t.priority_label || this.getPriorityLabel(t.priority);

            html += `
                <div class="logical-order-card ${isNext ? 'is-next-dispatch' : ''}">
                    <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
                        <span class="logical-order-rank">${rankLabel}</span>
                        <div style="min-width: 0;">
                            <div style="font-size: 0.84rem; font-weight: 700; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${t.title}">
                                ${t.title}
                            </div>
                            <div class="logical-order-meta">
                                <span>Task #${t.task_id}</span>
                                <span>&bull;</span>
                                <span>Seq #${t.insertion_sequence}</span>
                                <span>&bull;</span>
                                <span style="font-family: var(--font-mono); color: var(--brand-indigo);">Heap Index: [${t.heap_index}]</span>
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                        <span class="badge badge-p${t.priority}">P${t.priority} &bull; ${prioLabel}</span>
                        ${isNext ? '<span class="badge badge-completed">SLA Priority Root</span>' : ''}
                    </div>
                </div>
            `;
        });

        this.logicalOrderContainer.innerHTML = html;
    }

    renderTraceSteps(steps) {
        if (!this.traceContainer) return;

        if (!steps || steps.length === 0) {
            this.traceContainer.innerHTML = '<span>Heap holding invariant. Root task has highest SLA priority.</span>';
            return;
        }

        let html = '';
        steps.forEach((step, idx) => {
            let label = '';
            if (step.action === 'insert') {
                label = `+ Appended "${step.task}" at [${step.index}] (P${step.priority})`;
            } else if (step.action === 'compare') {
                label = `? Compare [${step.child_index}] vs Parent [${step.parent_index}]: ${step.swap_needed ? 'Swap required' : 'Invariant satisfied'}`;
            } else if (step.action === 'swap') {
                label = `&#8644; Swap [${step.index_a}] ${step.task_a} &harr; [${step.index_b}] ${step.task_b}`;
            } else if (step.action === 'sift_up_complete') {
                label = `&#10003; Sift-up settled at index [${step.final_index}]`;
            } else if (step.action === 'extract_start') {
                label = `&#9654; Selected Root [0] ${step.task} (P${step.priority})`;
            } else if (step.action === 'remove_root') {
                label = `&#10006; Removed root task from heap`;
            } else if (step.action === 'replace_root') {
                label = `&#8635; Moved last element to Root: ${step.task}`;
            } else if (step.action === 'compare_children') {
                label = `? Compared Left vs Right children &rarr; Selected [${step.selected_child_index}]`;
            } else if (step.action === 'compare_parent_child') {
                label = `? Compare Parent [${step.parent_index}] vs Child [${step.child_index}]: ${step.swap_needed ? 'Swap' : 'OK'}`;
            } else if (step.action === 'sift_down_complete') {
                label = `&#10003; Sift-down complete; root invariant restored`;
            } else {
                label = `${step.action}: ${step.reason || ''}`;
            }

            html += `<span style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; padding: 3px 8px; font-size: 0.74rem;">${idx + 1}. ${label}</span>`;
        });

        this.traceContainer.innerHTML = html;
    }
}
