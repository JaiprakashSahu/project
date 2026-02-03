// charts.js
// Chart.js Dark Theme Configuration
// Expects window.__CHART_DATA__ to be present (injected by template) OR will fetch from /api/dashboard-data

// Store chart instances for proper cleanup
window.chartInstances = window.chartInstances || {};

// Configure Chart.js defaults for dark backgrounds
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = 'rgba(255, 255, 255, 0.6)'; // Axis labels
  Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)'; // Gridlines

  // Global chart options
  Chart.defaults.plugins.legend.labels.color = 'rgba(255, 255, 255, 0.8)';
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(19, 19, 26, 0.95)';
  Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
  Chart.defaults.plugins.tooltip.bodyColor = 'rgba(255, 255, 255, 0.8)';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.2)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;

  // Scale options for better readability
  Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.1)';
  Chart.defaults.scale.ticks.color = 'rgba(255, 255, 255, 0.6)';
}


async function fetchChartData() {
  if (window.__CHART_DATA__) {
    return window.__CHART_DATA__;
  }

  try {
    const resp = await fetch("/api/dashboard-data");
    if (!resp.ok) {
      return null; // Silently return null if endpoint doesn't exist
    }
    return await resp.json();
  } catch (err) {
    console.log("Chart data not available on this page");
    return null;
  }
}

function createDonut(canvas, labels, values) {
  if (!canvas) return;
  
  // Destroy existing chart instance using Chart.js built-in method
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }
  
  const ctx = canvas.getContext('2d');
  const chartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: [
          '#2f8de1', '#dfe0e2', '#bfbfbf', '#13a2b3', '#29c07a'
        ],
        borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      cutout: '60%',
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index' }
      }
    }
  });
  
  // Store the chart instance for future cleanup
  window.chartInstances[canvas.id] = chartInstance;
}

function createLine(canvas, labels, values) {
  if (!canvas) return;
  
  // Destroy existing chart instance using Chart.js built-in method
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }
  
  const ctx = canvas.getContext('2d');
  const chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Spending',
        data: values,
        tension: 0.3,
        pointRadius: 4,
        borderWidth: 2,
        fill: false,
      }]
    },
    options: {
      scales: {
        x: { display: true },
        y: { display: true, beginAtZero: false }
      },
      plugins: { legend: { display: false } }
    }
  });
  
  // Store the chart instance for future cleanup
  window.chartInstances[canvas.id] = chartInstance;
}

// Function to destroy all chart instances
function destroyAllCharts() {
  Object.keys(window.chartInstances).forEach(chartId => {
    if (window.chartInstances[chartId]) {
      window.chartInstances[chartId].destroy();
      delete window.chartInstances[chartId];
    }
  });
}

async function initCharts() {
  try {
    // Check if we're on the analytics page that has its own chart handling
    if (document.querySelector('.analytics-dashboard')) {
      console.log("Analytics page detected - skipping charts.js initialization");
      return;
    }
    
    // Destroy any existing charts first
    destroyAllCharts();
    
    const d = await fetchChartData();

    // Exit early if no data available
    if (!d) {
      console.log("No chart data available");
      return;
    }

    // If server serialized JSON as string already, ensure object
    const data = (typeof d === "string") ? JSON.parse(d) : d;

    // Only create charts if the canvas elements exist and don't have existing Chart instances
    const donutCanvas = document.getElementById('donutChart');
    if (donutCanvas && !Chart.getChart(donutCanvas) && data.donut_labels && data.donut_values) {
      createDonut(donutCanvas, data.donut_labels, data.donut_values);
    }

    // Mini donut
    const mini = document.getElementById('miniDonut');
    if (mini && !Chart.getChart(mini) && data.mini_labels && data.mini_values) {
      createDonut(mini, data.mini_labels, data.mini_values);
    }

    // Line chart
    const line = document.getElementById('lineChart');
    if (line && !Chart.getChart(line) && data.line_labels && data.line_values) {
      createLine(line, data.line_labels, data.line_values);
    }

  } catch (err) {
    console.error("Failed to init charts", err);
  }
}

// Initialize charts when DOM is ready
document.addEventListener("DOMContentLoaded", initCharts);

// Also expose initCharts globally for manual refresh
window.initCharts = initCharts;
window.destroyAllCharts = destroyAllCharts;