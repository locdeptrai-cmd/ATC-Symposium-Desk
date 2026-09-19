(function () {
  var audioFile = null;
  var excelFile = None;

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(text, kind) {
    var el = $("ftStatus");
    if (!el) return;
    el.textContent = text || "";
    el.className = "status" + (kind ? " is-" + kind : "");
  }

  function setBar(pct) {
    var wrap = $("ftBarWrap");
    var bar = $("ftBar");
    if (wrap) wrap.hidden = pct == null;
    if (bar && pct != null) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
  }

  function renderStats(stats) {
    var el = $("ftStats");
    if (!el || !stats) return;
    var c = stats.counts || {};
    el.textContent =
      (c.total || 0) +
      " lượt gold · train " +
      (c.train || 0) +
      " · dev " +
      (c.dev || 0) +
      " · test " +
      (c.test || 0) +
      " · có audio " +
      (c.with_audio || 0) +
      " · " +
      (stats.rule_count || 0) +
      " cụm sửa đã lưu.";
    if (!($("ftLearned") && $("ftLearned").children.length)) {
      renderLearned(stats.rules || []);
    }
  }

  function renderLearned(rules) {
    var list = $("ftLearned");
    if (!list) return;
    if (!rules || !rules.length) {
      list.innerHTML = "<li class=\"rec-empty\">Chưa có cụm học từ Excel. Nạp một cặp băng + gold.</li>";
      return;
    }
    list.innerHTML = rules
      .slice(0, 40)
      .map(function (r) {
        return (
          "<li><strong>" +
          escapeHtml(r.src) +
          " → " +
          escapeHtml(r.dst) +
          "</strong><p>×" +
          escapeHtml(String(r.count || 1)) +
          "</p></li>"
        );
      })
      .join("");
  }

  function renderPreview(rows) {
    var body = $("ftPreview");
    if (!body) return;
    if (!rows || !rows.length) {
      body.innerHTML = "<tr><td colspan=\"4\" class=\"meta\">Chưa có xem trước.</td></tr>";
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        var t = Number(r.t_start);
        var clock = isFinite(t)
          ? Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0")
          : "—";
        return (
          "<tr><td>" +
          escapeHtml(clock) +
          "</td><td>" +
          escapeHtml(r.speaker || "") +
          "</td><td>" +
          escapeHtml(r.gold || "") +
          "</td><td>" +
          escapeHtml(r.asr || "") +
          "</td></tr>"
        );
      })
      .join("");
  }

  function loadStatus() {
    fetch("/api/finetune/status", { cache: "no-store" })
      .then(function (res) {
        return res.json();
      })
      .then(renderStats)
      .catch(function () {
        setStatus("Không đọc được corpus (cần chạy CHAY.cmd).", "warn");
      });
  }

  function poll(jobId) {
    fetch("/api/finetune/job?id=" + encodeURIComponent(jobId), { cache: "no-store" })
      .then(function (res) {
        return res.json();
      })
      .then(function (job) {
        if (!job || job.ok === false && !job.id) {
          throw new Error((job && job.error) || "Mất tiến trình.");
        }
        setBar(job.percent);
        setStatus(job.stage || "Đang xử lý…", job.error ? "warn" : "live");
        if (job.preview) renderPreview(job.preview);
        if (job.learned) renderLearned(job.learned);
        if (job.error && job.done) {
          setStatus(job.error, "warn");
          return;
        }
        if (job.done) {
          setBar(100);
          setStatus(
            "Đã nạp " + (job.gold_added || 0) + " lượt gold. Cách ghi VHF đã cập nhật cho REDA.",
            "ok"
          );
          if (job.stats) renderStats(job.stats);
          return;
        }
        setTimeout(function () {
          poll(jobId);
        }, 600);
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Lỗi fine-tune.", "warn");
      });
  }

  function submit() {
    if (!excelFile) {
      setStatus("Chọn file Excel nội dung hội thoại.", "warn");
      return;
    }
    var data = new FormData();
    data.append("excel", excelFile, excelFile.name);
    if (audioFile) data.append("audio", audioFile, audioFile.name);
    setStatus("Đang gửi file…", "live");
    setBar(3);
    fetch("/api/finetune/ingest", { method: "POST", body: data })
      .then(function (res) {
        return res.json();
      })
      .then(function (payload) {
        if (!payload || !payload.ok || !payload.id) {
          throw new Error((payload && payload.error) || "Không nạp được.");
        }
        poll(payload.id);
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Không gửi được.", "warn");
        setBar(null);
      });
  }

  function bind() {
    var audio = $("ftAudio");
    var excel = $("ftExcel");
    if (audio) {
      audio.addEventListener("change", function () {
        audioFile = this.files && this.files[0];
        if ($("ftAudioName")) {
          $("ftAudioName").textContent = audioFile ? audioFile.name : "AVI, MP4, WAV, MP3…";
        }
      });
    }
    if (excel) {
      excel.addEventListener("change", function () {
        excelFile = this.files && this.files[0];
        if ($("ftExcelName")) {
          $("ftExcelName").textContent = excelFile ? excelFile.name : ".xlsx nội dung đúng";
        }
      });
    }
    if ($("ftSubmit")) $("ftSubmit").addEventListener("click", submit);
    if ($("ftRefresh")) $("ftRefresh").addEventListener("click", loadStatus);
    loadStatus();
  }

  bind();
})();
