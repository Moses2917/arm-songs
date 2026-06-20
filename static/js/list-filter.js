(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    document.querySelectorAll("[data-filter-target]").forEach(function (input) {
      var sel = input.getAttribute("data-filter-target");
      var list = document.querySelector(sel);
      if (!list) return;

      var items = Array.prototype.slice.call(list.querySelectorAll("li"));
      var empty = document.createElement("p");
      empty.className = "filter-empty";
      empty.textContent = "Այս էջում համընկնող երգ չկա։";
      empty.style.display = "none";
      list.parentNode.insertBefore(empty, list.nextSibling);

      input.addEventListener("input", function () {
        var q = input.value.trim().toLowerCase();
        var shown = 0;
        items.forEach(function (li) {
          var match = !q || li.textContent.toLowerCase().indexOf(q) !== -1;
          li.style.display = match ? "" : "none";
          if (match) shown++;
        });
        empty.style.display = shown ? "none" : "block";
      });
    });
  });
})();
