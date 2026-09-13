(function () {
  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  var roleSel = document.getElementById("role");
  (ATC.ROLES || []).forEach(function (r) {
    var o = document.createElement("option");
    o.value = r.id;
    o.textContent = r.vi + " — " + r.en;
    roleSel.appendChild(o);
  });
  roleSel.value = "delegate";

  var order = [
    "sms_frms",
    "swim",
    "pbn",
    "atfm_capacity",
    "staffing",
    "language",
    "cns",
    "safety",
    "acdm",
    "general"
  ];

  function render() {
    var role = roleSel.value || "delegate";
    var html = order
      .map(function (id) {
        var pack = ATC.TOPIC_PACKS[id];
        if (!pack) return "";
        var points = (pack.points || [])
          .map(function (p, i) {
            return (
              "<li><span class=\"n\">" +
              (i + 1) +
              "</span><div><p class=\"en\">" +
              escapeHtml(p.en) +
              "</p><p class=\"vi\">" +
              escapeHtml(p.vi) +
              "</p></div></li>"
            );
          })
          .join("");
        var gloss = (pack.glossary || []).join(" · ");
        var body = (pack.bodies && pack.bodies[role]) || "";
        return (
          "<article class=\"card brief\">" +
          "<h3>" +
          escapeHtml(pack.label.vi) +
          " <span class=\"meta\">" +
          escapeHtml(pack.label.en) +
          "</span></h3>" +
          "<p class=\"gist\">" +
          escapeHtml(pack.gistVi) +
          "</p>" +
          "<p class=\"en-block\" style=\"font-size:1rem\">" +
          escapeHtml(body) +
          "</p>" +
          "<ul class=\"points\">" +
          points +
          "</ul>" +
          "<p class=\"meta\">" +
          escapeHtml(gloss) +
          "</p>" +
          "</article>"
        );
      })
      .join("");
    document.getElementById("briefs").innerHTML = html;
  }

  roleSel.addEventListener("change", render);
  render();
})();
