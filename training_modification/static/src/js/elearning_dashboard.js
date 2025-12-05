/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, onMounted, onWillUnmount } from "@odoo/owl";

class ELearningDashboard extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.ui = useService("ui");
        this.state = useState({
            loading: true,
            kpis: {
                totalCourses: 0,
                totalStudents: 0,
                activeCourses: 0,
                completedCourses: 0,
                totalContent: 0,
                attendanceRecords: 0,
                mailingCampaigns: 0,
                totalCertificates: 0,
                quizzes: 0,
                CourseRatings: 0,
                employeesEnrolledThisMonth: 0,
                pendingCourses: 0,
            },
            chartData: {},
        });

        onWillStart(() => this.fetchKPIs());

        onMounted(() => {
            this._interval = setInterval(() => this.fetchKPIs(), 60000);
            // Wait for Chart.js to load before rendering charts
            this.waitForChartJS().then(() => {
                this.renderCharts();
            });
            this.updateClock();
            this._clockInterval = setInterval(() => this.updateClock(), 1000);
        });

        onWillUnmount(() => {
            if (this._interval) clearInterval(this._interval);
            if (this._clockInterval) clearInterval(this._clockInterval);
            if (this.CourseProgressChartInstance) this.CourseProgressChartInstance.destroy();
            if (this.enrollmentsChartInstance) this.enrollmentsChartInstance.destroy();
            if (this.attendanceChartInstance) this.attendanceChartInstance.destroy();
            if (this.completionRatesChartInstance) this.completionRatesChartInstance.destroy();
            if (this.progressPieChartInstance) this.progressPieChartInstance.destroy();
        });
    }

    // NEW METHOD: Wait for Chart.js to load
    waitForChartJS() {
        return new Promise((resolve) => {
            if (typeof Chart !== 'undefined') {
                resolve();
                return;
            }

            let attempts = 0;
            const maxAttempts = 50; // 5 seconds max wait
            const checkInterval = setInterval(() => {
                attempts++;
                if (typeof Chart !== 'undefined') {
                    clearInterval(checkInterval);
                    resolve();
                } else if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    console.error('Chart.js failed to load after 5 seconds');
                    resolve(); // Resolve anyway to prevent hanging
                }
            }, 100);
        });
    }

    updateClock = () => {
        const clockElement = document.getElementById('elearning_dashboard_time');
        if (clockElement) {
            const now = new Date();
            const options = {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: 'numeric',
                minute: 'numeric',
                second: 'numeric',
                hour12: true
            };
            clockElement.textContent = now.toLocaleString('en-US', options);
        }
    }

    async fetchKPIs() {
        try {
            this.state.loading = true;
            const result = await this.orm.call(
                "elearning.dashboard.service",
                "get_dashboard_data",
                [],
                {}
            );
            this.state.kpis = Object.assign(this.state.kpis, result.kpis || {});
            this.state.chartData = result.chartData || {};

            await this.waitForChartJS();
            setTimeout(() => {
                this.renderCharts();
            }, 100);
        } catch (e) {
            console.warn("eLearning Dashboard fetch failed", e);
        } finally {
            this.state.loading = false;
        }
    }

    openModel = (model) => {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: model,
            res_model: model,
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            target: "current",
        });
    }

    renderCharts = () => {
        // Check if Chart.js is available
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded. Charts cannot be rendered.');
            return;
        }

        setTimeout(() => {
            this.renderCourseProgressChart();
            this.renderEnrollmentsChart();
            this.renderAttendanceChart();
            this.renderCompletionRatesChart();
            this.renderProgressPieChart();
        }, 100);
    }

    renderCourseProgressChart = () => {
        const canvas = document.getElementById('CourseProgressChart');
        if (!canvas || typeof Chart === 'undefined' || !this.state.chartData.CourseProgressChart) return;

        const ctx = canvas.getContext('2d');
        const data = this.state.chartData.CourseProgressChart;

        if (this.CourseProgressChartInstance) {
            this.CourseProgressChartInstance.destroy();
        }

        this.CourseProgressChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.course),
                datasets: [{
                    label: 'Not Started',
                    data: data.map(item => item.notStarted),
                    backgroundColor: '#e74c3c',
                    stack: 'Stack 0',
                }, {
                    label: 'In Progress',
                    data: data.map(item => item.inProgress),
                    backgroundColor: '#f39c12',
                    stack: 'Stack 0',
                }, {
                    label: 'Completed',
                    data: data.map(item => item.completed),
                    backgroundColor: '#27ae60',
                    stack: 'Stack 0',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Course Progress Overview',
                        font: { size: 16, weight: 'bold' },
                        color: '#2c3e50',
                        padding: 20
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });
    }

    renderEnrollmentsChart = () => {
        const canvas = document.getElementById('enrollmentsChart');
        if (!canvas || typeof Chart === 'undefined' || !this.state.chartData.enrollmentsByMonth) return;

        const ctx = canvas.getContext('2d');
        const data = this.state.chartData.enrollmentsByMonth;

        if (this.enrollmentsChartInstance) {
            this.enrollmentsChartInstance.destroy();
        }

        this.enrollmentsChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.month),
                datasets: [{
                    label: 'Enrollments',
                    data: data.map(item => item.enrollments),
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#3498db',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: '#2980b9',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Monthly Enrollment Trends',
                        font: { size: 16, weight: 'bold' },
                        color: '#2c3e50',
                        padding: 20
                    },
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(44, 62, 80, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#34495e',
                        borderWidth: 1,
                        cornerRadius: 8
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 5,
                            color: '#7f8c8d',
                            font: { size: 11 }
                        },
                        grid: {
                            color: 'rgba(127, 140, 141, 0.2)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: {
                            color: '#7f8c8d',
                            maxRotation: 45,
                            minRotation: 0,
                            font: { size: 10 }
                        },
                        grid: { display: false }
                    }
                },
                animation: {
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderAttendanceChart = () => {
        const canvas = document.getElementById('attendanceChart');
        if (!canvas || typeof Chart === 'undefined' || !this.state.chartData.attendanceByMonth) return;

        const ctx = canvas.getContext('2d');
        const data = this.state.chartData.attendanceByMonth;

        if (this.attendanceChartInstance) {
            this.attendanceChartInstance.destroy();
        }

        this.attendanceChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.month),
                datasets: [{
                    label: 'Attendance Rate (%)',
                    data: data.map(item => item.attendanceRate),
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#e74c3c',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 3,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Monthly Attendance Rates',
                        font: { size: 16, weight: 'bold' },
                        color: '#2c3e50',
                        padding: 20
                    },
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(44, 62, 80, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#34495e',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const item = data[context.dataIndex];
                                return [
                                    `Attendance Rate: ${context.parsed.y}%`,
                                    `Total Sessions: ${item.totalSessions}`,
                                    `Present: ${item.presentCount}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 10,
                            color: '#7f8c8d',
                            font: { size: 11 },
                            callback: function(value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: 'rgba(127, 140, 141, 0.2)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: {
                            color: '#7f8c8d',
                            maxRotation: 45,
                            minRotation: 0,
                            font: { size: 10 }
                        },
                        grid: { display: false }
                    }
                },
                animation: {
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderCompletionRatesChart = () => {
        const canvas = document.getElementById('completionRatesChart');
        if (!canvas || typeof Chart === 'undefined' || !this.state.chartData.completionRates) return;

        const ctx = canvas.getContext('2d');
        const data = this.state.chartData.completionRates;

        if (this.completionRatesChartInstance) {
            this.completionRatesChartInstance.destroy();
        }

        const colors = this.generateColors(data.length);

        this.completionRatesChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.courseName),
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: data.map(item => item.completionRate),
                    backgroundColor: colors.background,
                    borderColor: colors.border,
                    borderWidth: 2,
                    borderRadius: 6,
                    borderSkipped: false,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Course Completion Rates',
                        font: { size: 16, weight: 'bold' },
                        color: '#2c3e50',
                        padding: 20
                    },
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(44, 62, 80, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#34495e',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const item = data[context.dataIndex];
                                return [
                                    `Completion Rate: ${context.parsed.x}%`,
                                    `Completed: ${item.completed}/${item.totalEnrolled}`,
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 10,
                            color: '#7f8c8d',
                            font: { size: 11 },
                            callback: function(value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: 'rgba(127, 140, 141, 0.2)',
                            drawBorder: false
                        }
                    },
                    y: {
                        ticks: {
                            color: '#7f8c8d',
                            font: { size: 10 }
                        },
                        grid: { display: false }
                    }
                },
                animation: {
                    duration: 1000,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderProgressPieChart = () => {
        const canvas = document.getElementById('progressPieChart');
        if (!canvas || typeof Chart === 'undefined' || !this.state.chartData.studentProgress) return;

        const ctx = canvas.getContext('2d');
        const data = this.state.chartData.studentProgress;

        if (this.progressPieChartInstance) {
            this.progressPieChartInstance.destroy();
        }

        const colors = [
            '#e74c3c', // Not Started - Red
            '#f39c12', // In Progress - Orange
            '#27ae60', // Completed - Green
            '#3498db'  // Certified - Blue
        ];

        this.progressPieChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.status),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: colors.slice(0, data.length),
                    borderColor: '#fff',
                    borderWidth: 3,
                    hoverBorderWidth: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    title: {
                        display: true,
                        text: 'Employee Progress Distribution',
                        font: { size: 16, weight: 'bold' },
                        color: '#2c3e50',
                        padding: 20
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 11 },
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(44, 62, 80, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#34495e',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    generateColors = (count) => {
        const baseColors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
            '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43',
            '#10AC84', '#EE5A52', '#0652DD', '#9C88FF', '#FFC312',
            '#C44569', '#F8B500', '#6A89CC', '#82589F', '#2C3A47'
        ];

        const background = [];
        const border = [];

        for (let i = 0; i < count; i++) {
            const colorIndex = i % baseColors.length;
            background.push(baseColors[colorIndex] + '80');
            border.push(baseColors[colorIndex]);
        }

        return { background, border };
    }
}

ELearningDashboard.template = "elearning.ELearningDashboard";

registry.category("actions").add("elearning_dashboard.client_action", ELearningDashboard);