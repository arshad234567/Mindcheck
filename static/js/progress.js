// Updates the questionnaire progress bar as questions are answered.
// Scoring is NOT done here - it always happens on the server.
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("screening-form");
  if (!form) return;
  const bar = document.getElementById("progress-bar");
  const label = document.getElementById("progress-label");
  const total = parseInt(form.dataset.total, 10);

  function update() {
    const answered = new Set();
    form.querySelectorAll("input[type=radio]:checked").forEach(function (input) {
      answered.add(input.name);
    });
    const pct = Math.round((answered.size / total) * 100);
    bar.style.width = pct + "%";
    bar.setAttribute("aria-valuenow", pct);
    label.textContent = answered.size + " of " + total + " answered";
  }

  form.addEventListener("change", update);
  update();
});
