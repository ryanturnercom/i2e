// i2e console — live refresh. Subscribes to the SSE change channel and
// reloads when .i2e/ changes, unless the user is mid-edit in a field.
(function () {
  "use strict";
  function busy() {
    var el = document.activeElement;
    return el && ["INPUT", "TEXTAREA", "SELECT"].indexOf(el.tagName) !== -1;
  }
  try {
    var es = new EventSource("/events");
    var sawError = false;
    es.addEventListener("change", function () {
      if (!busy()) location.reload();
    });
    // After an auto-reload restart the server briefly disappears: the
    // EventSource errors, then reconnects once the fresh process is up.
    // Reload on that recovery so a code-change restart is hands-free.
    es.addEventListener("ready", function () {
      if (sawError && !busy()) location.reload();
    });
    es.onerror = function () {
      sawError = true;
    };
  } catch (e) {
    /* SSE unavailable — console still works without live refresh. */
  }

  // Escape closes an open action modal — expected modal-dialog behaviour.
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var modal = document.getElementById("action-modal");
    if (modal) modal.remove();
  });

  // Tweaks panel "Restart server" button: POST to the restart endpoint,
  // then reload the page after the configured delay so the browser
  // reconnects to the freshly re-execed server.
  var restartBtn = document.getElementById("restart-server");
  if (restartBtn) {
    restartBtn.addEventListener("click", function () {
      var url = restartBtn.getAttribute("data-restart-url") || "/restart";
      var delay = Number(restartBtn.getAttribute("data-reload-delay")) || 10000;
      restartBtn.disabled = true;
      restartBtn.textContent = "Restarting…";
      fetch(url, { method: "POST" }).catch(function () {});
      setTimeout(function () {
        location.reload();
      }, delay);
    });
  }
})();
