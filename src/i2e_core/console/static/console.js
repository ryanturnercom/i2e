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
    es.addEventListener("change", function () {
      if (!busy()) location.reload();
    });
  } catch (e) {
    /* SSE unavailable — console still works without live refresh. */
  }

  // Escape closes an open action modal — expected modal-dialog behaviour.
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var modal = document.getElementById("action-modal");
    if (modal) modal.remove();
  });
})();
