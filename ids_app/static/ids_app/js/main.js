// Auto-scroll the terminal-style log console to the latest line, and draw
// the Chart.js bar charts (class distribution / algorithm comparison)
// using dark-on-light styling to match the page's white panels.
document.addEventListener("DOMContentLoaded", function () {
  var body = document.getElementById("console-body");
  if (body) body.scrollTop = body.scrollHeight;

  var CYAN = "#00b8d9";
  var MAGENTA = "#e0389a";
  var GOLD = "#d99a1b";
  var VIOLET = "#7c4dff";
  var TEXT = "#171a2b";
  var TEXT_DIM = "#6b7280";
  var GRID = "rgba(23,26,43,0.08)";

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  // ---- Class distribution bar chart -------------------------------
  var labelData = readJSON("label-chart-data");
  var labelCanvas = document.getElementById("labelChart");
  if (labelData && labelCanvas) {
    var palette = [CYAN, MAGENTA, GOLD, VIOLET, "#0a9b6f"];
    new Chart(labelCanvas, {
      type: "bar",
      data: {
        labels: labelData.labels,
        datasets: [
          {
            label: "Records",
            data: labelData.values,
            backgroundColor: labelData.labels.map(function (_, i) {
              return palette[i % palette.length];
            }),
            borderRadius: 6,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: TEXT_DIM }, grid: { color: GRID } },
          y: { ticks: { color: TEXT_DIM }, grid: { color: GRID }, beginAtZero: true },
        },
      },
    });
  }

  // ---- LSTM vs TCN comparison chart --------------------------------
  var compareData = readJSON("compare-chart-data");
  var compareCanvas = document.getElementById("compareChart");
  if (compareData && compareCanvas) {
    var seriesColors = { "Accuracy": CYAN, "Precision": MAGENTA, "Recall": GOLD, "F1 Score": VIOLET };
    var datasets = Object.keys(compareData.series).map(function (key) {
      return {
        label: key,
        data: compareData.series[key],
        backgroundColor: seriesColors[key] || CYAN,
        borderRadius: 6,
      };
    });
    new Chart(compareCanvas, {
      type: "bar",
      data: { labels: compareData.labels, datasets: datasets },
      options: {
        plugins: { legend: { labels: { color: TEXT } } },
        scales: {
          x: { ticks: { color: TEXT_DIM }, grid: { color: GRID } },
          y: { ticks: { color: TEXT_DIM }, grid: { color: GRID }, beginAtZero: true, max: 100 },
        },
      },
    });
  }
});
