(function (root) {
  "use strict";
  var ATC = root.ATC = root.ATC || {};

  // One running translation and one replaceable pending caption. Never queue
  // an entire speech behind a slow model, or attach an old translation to new EN.
  ATC.createCaptionStream = function (translate, render, now) {
    now = now || Date.now;
    var current = null, busy = false;
    function pump() {
      if (busy || !current || current.started) return;
      var item = current;
      item.started = true;
      busy = true;
      Promise.resolve().then(function () { return translate(item.text, item.opts); })
        .then(function (result) {
          if (current !== item) return;
          render({ text: item.text, translation: result.text, method: result.method,
            lag: now() - item.at, pending: false });
        }, function () {
          if (current === item) render({ text: item.text, translation: "", error: true });
        }).finally(function () { busy = false; pump(); });
    }
    return {
      push: function (text, opts) {
        text = String(text || "").replace(/\s+/g, " ").trim();
        var parts = text.match(/[^.!?;]+[.!?;]?/g) || [];
        var words = (parts.pop() || "").trim().split(/\s+/);
        text = words.slice(Math.floor((words.length - 1) / 12) * 12).join(" ");
        var key = JSON.stringify([text, opts.source, opts.sessionTopic]);
        if (!text || (current && current.key === key)) return;
        current = { text: text, key: key, opts: opts, at: now() };
        render({ text: text, translation: "", pending: true });
        pump();
      },
      reset: function () { current = null; render({ text: "", translation: "" }); }
    };
  };
  if (!root.document) return;
  var pip = null, opening = false, last = {}, button = document.getElementById("btnSubtitles");
  var hint = document.getElementById("subtitleHint");
  if (!button) return;
  function render(data) {
    last = data;
    if (!pip || pip.closed) return;
    pip.document.getElementById("captionSource").textContent = data.text || "Đang chờ lời nói…";
    pip.document.getElementById("captionTranslation").textContent = data.translation || (data.pending ? "Đang dịch…" : "");
    pip.document.getElementById("captionMeta").textContent = data.error ? "Chưa dịch được đoạn này" :
      data.pending ? "Mục tiêu bản dịch trễ ≤ 1 giây" : data.lag != null ?
        "Độ trễ dịch: " + (data.lag / 1000).toFixed(2) + " s" +
        (data.lag > 1000 ? " · vượt mục tiêu 1 s" : "") +
        (data.method === "on-device-mt" || data.method === "offline-library" ? "" : " · chỉ thay cụm từ, chưa có dịch đầy đủ") :
        "Bấm Nghe EN ở đây hoặc trong cửa sổ chính";
  }
  var stream = ATC.createCaptionStream(function (text, opts) {
    return ATC.translateChunkAsync(text, opts);
  }, render);
  ATC.floatingSubtitles = {
    push: function (text, opts) { if (pip && !pip.closed) stream.push(text, opts); },
    reset: function () { stream.reset(); }
  };
  button.addEventListener("click", async function () {
    if (opening) return;
    if (pip && !pip.closed) { pip.close(); return; }
    if (!root.documentPictureInPicture) {
      hint.textContent = "Trình duyệt này chưa hỗ trợ phụ đề nổi. Hãy mở bằng Chrome/Edge trên máy tính tại localhost hoặc HTTPS.";
      return;
    }
    opening = true;
    try {
      pip = await root.documentPictureInPicture.requestWindow({ width: 720, height: 270 });
      var doc = pip.document;
      doc.documentElement.lang = "vi";
      doc.title = "ATC · Phụ đề song ngữ";
      doc.head.innerHTML = '<meta name="viewport" content="width=device-width,initial-scale=1"><style>' +
        'body{margin:0;padding:18px;background:#101827;color:#fff;font:20px/1.45 system-ui}p{margin:10px 0;overflow-wrap:anywhere}' +
        '#captionTranslation{color:#ffe29a}small{font-size:12px;color:#bac7da}button{background:#25364e;color:white;border:1px solid #63738a;border-radius:6px;padding:5px 12px;margin-right:8px;cursor:pointer}' +
        '</style>';
      doc.body.innerHTML = '<nav><button id="listen">Nghe EN</button><button id="stop">Dừng nghe</button><button id="close">Đóng phụ đề</button></nav>' +
        '<p id="captionSource"></p><p id="captionTranslation" aria-live="polite"></p><small id="captionMeta"></small>';
      doc.getElementById("listen").onclick = function () { document.getElementById("btnEn").click(); };
      doc.getElementById("stop").onclick = function () { document.getElementById("btnStop").click(); };
      doc.getElementById("close").onclick = function () { pip.close(); };
      pip.addEventListener("pagehide", function () {
        pip = null; stream.reset(); button.textContent = "Phụ đề nổi EN + VI";
        button.setAttribute("aria-pressed", "false");
      }, { once: true });
      button.textContent = "Đóng phụ đề nổi";
      button.setAttribute("aria-pressed", "true");
      hint.textContent = "Đã mở phụ đề nổi. Bạn có thể thu nhỏ cửa sổ chính; giữ tab và máy hoạt động. Không hiển thị trên màn hình khóa.";
      render(last);
      // Warm the local model under the user's click before backgrounding the app.
      ATC.ensureMt("en", "vi");
    } catch (err) {
      hint.textContent = "Không mở được phụ đề nổi: " + err.message;
    } finally { opening = false; }
  });
})(typeof window !== "undefined" ? window : globalThis);
