(function () {
  var audioFile = null;
  var excelFile = null;

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

  function formatBytes(n) {
    var v = Number(n) || 0;
    if (v < 1024) return v + " B";
    if (v < 1024 * 1024) return (v / 1024).toFixed(1) + " KB";
    return (v / (1024 * 1024)).toFixed(1) + " MB";
  }

  function isExcel(file) {
    var name = String((file && file.name) || "").toLowerCase();
    var type = String((file && file.type) || "").toLowerCase();
    if (/\.(xlsx|xls|csv)$/.test(name)) return true;
    return type.indexOf("sheet") >= 0 || type.indexOf("excel") >= 0 || type === "text/csv";
  }

  function isAudio(file) {
    var name = String((file && file.name) || "").toLowerCase();
    var type = String((file && file.type) || "").toLowerCase();
    if (type.indexOf("audio/") === 0 || type.indexOf("video/") === 0) return true;
    return /\.(avi|mp4|m4v|mov|mkv|webm|mpeg|mpg|wav|mp3|m4a|aac|ogg|flac|wma|aiff|aif)$/.test(name);
  }

  function takeFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []).filter(Boolean);
    if (!files.length) return;
    var skipped = 0;
    files.forEach(function (file) {
      if (isExcel(file)) {
        excelFile = file;
        if ($("ftExcelName")) $("ftExcelName").textContent = file.name;
      } else if (isAudio(file)) {
        audioFile = file;
        if ($("ftAudioName")) $("ftAudioName").textContent = file.name;
      } else {
        skipped += 1;
      }
    });
    if (!excelFile && !audioFile) {
      setStatus("Không nhận file hội thoại. Cần .xlsx/.csv và băng AVI/MP4/WAV…", "warn");
      return;
    }
    var bits = [];
    if (audioFile) bits.push(audioFile.name);
    if (excelFile) bits.push(excelFile.name);
    var msg = "Đã chọn " + bits.join(" + ") + ". Bấm Nạp và cập nhật cách ghi.";
    if (!excelFile) msg = "Đã chọn băng. Còn thiếu file Excel hội thoại.";
    if (skipped) msg += " Bỏ qua " + skipped + " file không dùng được.";
    setStatus(msg, excelFile ? "ok" : "warn");
  }

  function bindDrop(el) {
    if (!el) return;
    ["dragenter", "dragover"].forEach(function (ev) {
      el.addEventListener(ev, function (e) {
        e.preventDefault();
        e.stopPropagation();
        el.classList.add("is-over");
      });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      el.addEventListener(ev, function () {
        el.classList.remove("is-over");
      });
    });
    el.addEventListener("drop", function (e) {
      e.preventDefault();
      e.stopPropagation();
      takeFiles(e.dataTransfer && e.dataTransfer.files);
    });
  }

  function renderRecipe(recipe) {
    var el = $("ftRecipe");
    if (!el || !recipe) return;
    var mix = (recipe.mix_counts || {}).total || 0;
    el.textContent =
      "Runtime REDA: turbo Singularity" +
      (recipe.runtime_ready ? " (sẵn sàng)" : " (chưa thấy CT2)") +
      " · A/B tclin: " +
      (recipe.ab_ready ? "đã convert CT2" : "chưa convert — python tools/asr_dataset/export_ct2.py --preset tclin") +
      " · Mix ATCO2-1h: " +
      mix +
      " câu · LoRA base: " +
      (recipe.train_base || "") +
      " (70/30).";
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
      " cụm sửa đã lưu · " +
      (stats.glossary_phrase_count || 0) +
      " phraseology đã nạp.";
    if (stats.recipe) renderRecipe(stats.recipe);
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
        if (!job || (job.ok === false && !job.id)) {
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
            job.stage ||
              ("Đã nạp " + (job.gold_added || 0) + " lượt gold. Cách ghi VHF đã cập nhật cho REDA."),
            "ok"
          );
          if (job.stats) renderStats(job.stats);
          else loadStatus();
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
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/finetune/ingest");
    xhr.upload.onprogress = function (ev) {
      if (!ev.lengthComputable) return;
      var pct = 3 + Math.round((ev.loaded / ev.total) * 15);
      setBar(pct);
      setStatus(
        "Đang gửi file… " + formatBytes(ev.loaded) + " / " + formatBytes(ev.total),
        "live"
      );
    };
    xhr.onerror = function () {
      setStatus("Không gửi được. Kiểm tra CHAY.cmd còn chạy.", "warn");
      setBar(null);
    };
    xhr.onload = function () {
      var payload = {};
      try {
        payload = JSON.parse(xhr.responseText || "{}");
      } catch (e) {
        setStatus("Máy chủ trả lời không hợp lệ. Thử tải lại trang (Ctrl+F5).", "warn");
        setBar(null);
        return;
      }
      if (xhr.status >= 400 || !payload.ok || !payload.id) {
        setStatus((payload && payload.error) || "Không nạp được.", "warn");
        setBar(null);
        return;
      }
      poll(payload.id);
    };
    xhr.send(data);
  }

  function evalWer() {
    setStatus("Đang đo WER trên bản sửa HUMAN…", "live");
    fetch("/api/finetune/eval", { cache: "no-store" })
      .then(function (res) {
        return res.json();
      })
      .then(function (payload) {
        if (!payload || payload.ok === false) {
          throw new Error((payload && payload.error) || "Không đo được WER.");
        }
        var n = payload.n || 0;
        if (!n) {
          setStatus("Chưa có cặp HUMAN/ASR để đo. Sửa kịch bản trên REDA rồi đo lại.", "warn");
          return;
        }
        setStatus(
          "WER gold " +
            (payload.wer != null ? Number(payload.wer).toFixed(3) : "—") +
            " · CER " +
            (payload.cer != null ? Number(payload.cer).toFixed(3) : "—") +
            " · n=" +
            n +
            ".",
          "ok"
        );
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Không đo được WER.", "warn");
      });
  }

  function prepareMix() {
    setStatus("Đang nạp ATCO2-test-set-1h (Hugging Face, ~110 MB)…", "live");
    setBar(3);
    fetch("/api/finetune/prepare-mix", { method: "POST" })
      .then(function (res) {
        return res.json();
      })
      .then(function (payload) {
        if (!payload || payload.ok === false || !payload.id) {
          throw new Error((payload && payload.error) || "Không nạp được ATCO2-1h.");
        }
        poll(payload.id);
      })
      .catch(function (err) {
        setBar(null);
        setStatus((err && err.message) || "Không nạp được ATCO2-1h. Cần mạng và pip install datasets.", "warn");
      });
  }

  function seedGlossary() {
    setStatus("Đang nạp phraseology từ Thuật ngữ…", "live");
    fetch("/api/finetune/seed-glossary", { method: "POST" })
      .then(function (res) {
        return res.json();
      })
      .then(function (payload) {
        if (!payload || payload.ok === false) {
          throw new Error((payload && payload.error) || "Không nạp được phraseology.");
        }
        setStatus(
          "Đã nạp " + (payload.count || 0) + " cụm phraseology vào hotwords cho ghi lời.",
          "ok"
        );
        if (payload.stats) renderStats(payload.stats);
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Không nạp được phraseology.", "warn");
      });
  }

  function bind() {
    var audio = $("ftAudio");
    var excel = $("ftExcel");
    bindDrop($("ftAudioDrop"));
    bindDrop($("ftExcelDrop"));
    bindDrop($("ftDropGrid"));
    window.addEventListener("dragover", function (e) {
      e.preventDefault();
    });
    window.addEventListener("drop", function (e) {
      e.preventDefault();
      takeFiles(e.dataTransfer && e.dataTransfer.files);
    });
    if (audio) {
      audio.addEventListener("change", function () {
        takeFiles(this.files);
        this.value = "";
      });
    }
    if (excel) {
      excel.addEventListener("change", function () {
        takeFiles(this.files);
        this.value = "";
      });
    }
    if ($("ftSubmit")) $("ftSubmit").addEventListener("click", submit);
    if ($("ftRefresh")) $("ftRefresh").addEventListener("click", loadStatus);
    if ($("ftSeedGlossary")) $("ftSeedGlossary").addEventListener("click", seedGlossary);
    if ($("ftEvalWer")) $("ftEvalWer").addEventListener("click", evalWer);
    if ($("ftPrepareMix")) $("ftPrepareMix").addEventListener("click", prepareMix);
    loadStatus();
  }

  bind();
})();
