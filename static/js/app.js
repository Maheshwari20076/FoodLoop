// FoodLoop — small shared front-end behaviors

document.addEventListener("DOMContentLoaded", function () {
  // Auto-submit filter forms on change
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () {
      el.closest("form").submit();
    });
  });

  // Confirm dialogs for destructive actions
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      if (!confirm(el.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // Auto-dismiss flash alerts
  document.querySelectorAll(".alert.auto-dismiss").forEach(function (el) {
    setTimeout(function () {
      el.classList.add("fade");
      el.classList.remove("show");
      setTimeout(() => el.remove(), 400);
    }, 4500);
  });

  // Live countdown timers for elements with data-countdown="ISO_DATETIME"
  document.querySelectorAll("[data-countdown]").forEach(function (el) {
    const target = new Date(el.getAttribute("data-countdown"));
    function tick() {
      const now = new Date();
      let diff = Math.max(0, (target - now) / 1000);
      if (diff <= 0) {
        el.textContent = "Expired";
        el.classList.add("text-danger");
        return;
      }
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = Math.floor(diff % 60);
      if (h >= 24) {
        const d = Math.floor(h / 24);
        el.textContent = `${d}d ${h % 24}h`;
      } else {
        el.textContent = `${h}h ${m}m ${s}s`;
      }
    }
    tick();
    setInterval(tick, 1000);
  });

  // Image preview on file input
  const imageInput = document.getElementById("image");
  const imagePreview = document.getElementById("imagePreview");
  if (imageInput && imagePreview) {
    imageInput.addEventListener("change", function () {
      const file = imageInput.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          imagePreview.src = e.target.result;
          imagePreview.classList.remove("d-none");
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Copy pickup code
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const text = btn.getAttribute("data-copy");
      navigator.clipboard.writeText(text).then(() => {
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i> Copied';
        setTimeout(() => (btn.innerHTML = original), 1500);
      });
    });
  });
});
