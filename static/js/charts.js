/**
 * PriorityFlow - Chart.js SaaS Performance & Overview Analytics
 * ==============================================================
 * Renders:
 * 1. Overview Priority Distribution Donut (#overview-priority-chart)
 * 2. Overview Task Status Distribution Donut (#overview-status-chart)
 * 3. Analytics Priority Distribution Donut (#chart-priority-distribution)
 * 4. Analytics SLA Latency Breakdown Bar (#chart-latency-breakdown)
 */

class ChartsManager {
    constructor() {
        this.overviewPriorityChart = null;
        this.overviewStatusChart = null;
        this.analyticsPriorityChart = null;
        this.analyticsLatencyChart = null;
        this.initCharts();
    }

    initCharts() {
        if (!window.Chart) return;

        // -------------------------------------------------------------
        // 1. Overview: Priority Distribution Donut
        // -------------------------------------------------------------
        const opCtx = document.getElementById('overview-priority-chart');
        if (opCtx) {
            this.overviewPriorityChart = new Chart(opCtx, {
                type: 'doughnut',
                data: {
                    labels: ['P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low', 'P5 Background'],
                    datasets: [{
                        data: [0, 0, 0, 0, 0],
                        backgroundColor: ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#64748b'],
                        borderColor: '#ffffff',
                        borderWidth: 3,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#334155', boxWidth: 12, font: { size: 11, family: 'Inter', weight: 500 } }
                        }
                    },
                    cutout: '66%'
                }
            });
        }

        // -------------------------------------------------------------
        // 2. Overview: Task Status Distribution Donut
        // -------------------------------------------------------------
        const osCtx = document.getElementById('overview-status-chart');
        if (osCtx) {
            this.overviewStatusChart = new Chart(osCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Pending (Queued)', 'In-Progress', 'Completed', 'Cancelled'],
                    datasets: [{
                        data: [0, 0, 0, 0],
                        backgroundColor: ['#6366f1', '#3b82f6', '#10b981', '#ef4444'],
                        borderColor: '#ffffff',
                        borderWidth: 3,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#334155', boxWidth: 12, font: { size: 11, family: 'Inter', weight: 500 } }
                        }
                    },
                    cutout: '66%'
                }
            });
        }

        // -------------------------------------------------------------
        // 3. Analytics: Priority Tier Donut
        // -------------------------------------------------------------
        const prioCtx = document.getElementById('chart-priority-distribution');
        if (prioCtx) {
            this.analyticsPriorityChart = new Chart(prioCtx, {
                type: 'doughnut',
                data: {
                    labels: ['P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low', 'P5 Background'],
                    datasets: [{
                        data: [0, 0, 0, 0, 0],
                        backgroundColor: ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#64748b'],
                        borderColor: '#ffffff',
                        borderWidth: 3,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#334155', boxWidth: 12, font: { size: 11, family: 'Inter', weight: 500 } }
                        }
                    },
                    cutout: '66%'
                }
            });
        }

        // -------------------------------------------------------------
        // 4. Analytics: Latency Bar Chart
        // -------------------------------------------------------------
        const latencyCtx = document.getElementById('chart-latency-breakdown');
        if (latencyCtx) {
            this.analyticsLatencyChart = new Chart(latencyCtx, {
                type: 'bar',
                data: {
                    labels: ['P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low', 'P5 Background'],
                    datasets: [{
                        label: 'Mean Wait Latency (Sec)',
                        data: [0.8, 3.2, 8.5, 18.0, 42.0],
                        backgroundColor: [
                            'rgba(239, 68, 68, 0.85)',
                            'rgba(249, 115, 22, 0.85)',
                            'rgba(234, 179, 8, 0.85)',
                            'rgba(59, 130, 246, 0.85)',
                            'rgba(100, 116, 139, 0.85)'
                        ],
                        borderColor: ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#64748b'],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#64748b', font: { size: 11, family: 'Inter' } }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: '#64748b', font: { size: 11, family: 'Inter' } }, grid: { color: '#f1f5f9' } }
                    }
                }
            });
        }
    }

    /**
     * Updates Overview Charts with dynamic SQLite data.
     */
    updateOverviewCharts(priorityDist, statusDist) {
        if (this.overviewPriorityChart && priorityDist) {
            this.overviewPriorityChart.data.datasets[0].data = [
                priorityDist['1'] || priorityDist[1] || 0,
                priorityDist['2'] || priorityDist[2] || 0,
                priorityDist['3'] || priorityDist[3] || 0,
                priorityDist['4'] || priorityDist[4] || 0,
                priorityDist['5'] || priorityDist[5] || 0,
            ];
            this.overviewPriorityChart.update();
        }

        if (this.overviewStatusChart && statusDist) {
            this.overviewStatusChart.data.datasets[0].data = [
                statusDist['Pending'] || statusDist['QUEUED'] || 0,
                statusDist['In-Progress'] || statusDist['PROCESSING'] || 0,
                statusDist['Completed'] || statusDist['COMPLETED'] || 0,
                statusDist['Cancelled'] || statusDist['CANCELLED'] || 0,
            ];
            this.overviewStatusChart.update();
        }
    }

    /**
     * Updates Analytics Charts.
     */
    updateAnalytics(analytics) {
        if (!analytics) return;

        if (this.analyticsPriorityChart && analytics.priority_distribution) {
            const dist = analytics.priority_distribution;
            this.analyticsPriorityChart.data.datasets[0].data = [
                dist['1'] || dist[1] || 0,
                dist['2'] || dist[2] || 0,
                dist['3'] || dist[3] || 0,
                dist['4'] || dist[4] || 0,
                dist['5'] || dist[5] || 0,
            ];
            this.analyticsPriorityChart.update();
        }

        if (this.analyticsLatencyChart && analytics.avg_latency_by_priority) {
            const l = analytics.avg_latency_by_priority;
            this.analyticsLatencyChart.data.datasets[0].data = [
                l['1'] || l[1] || 0.8,
                l['2'] || l[2] || 3.2,
                l['3'] || l[3] || 8.5,
                l['4'] || l[4] || 18.0,
                l['5'] || l[5] || 42.0,
            ];
            this.analyticsLatencyChart.update();
        }
    }
}
