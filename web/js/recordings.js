(function () {
  var DB_NAME = "atc-recordings";
  var DB_VER = 1;
  var STORE = "tapes";
  var ACCEPT_EXT = /\.(mp3|wav|m4a|aac|ogg|flac|webm|mp4|mov|mkv|m4v|avi)$/i;
  var VIDEO_EXT = /\.(mp4|mov|mkv|m4v|avi|webm)$/i;
  var MIME_BY_EXT = {
    mp3: "audio/mpeg",
    wav: "audio/wav",
    m4a: "audio/mp4",
    aac: "audio/aac",
    ogg: "audio/ogg",
    flac: "audio/flac",
    webm: "video/webm",
    mp4: "video/mp4",
    mov: "video/quicktime",
    mkv: "video/x-matroska",
    m4v: "video/x-m4v",
    avi: "video/x-msvideo"
  };

  function extOf(name) {
    var m = /\.([a-z0-9]+)$/i.exec(name || "");
    return m ? m[1].toLowerCase() : "";
  }

  function guessMime(file) {
    var type = String(file && file.type || "").toLowerCase();
    if (type === "video/avi" || type === "video/msvideo" || type === "application/x-troff-msvideo") {
      return "video/x-msvideo";
    }
    if (type.indexOf("audio/") === 0 || type.indexOf("video/") === 0) return type;
    return MIME_BY_EXT[extOf(file && file.name)] || type || "";
  }

  function playableBlob(blob, mime) {
    if (!blob || !mime) return blob;
    var cur = String(blob.type || "").toLowerCase();
    if (cur === mime) return blob;
    if (!cur || cur === "application/octet-stream" || cur === "video/avi" || cur === "video/msvideo") {
      return new Blob([blob], { type: mime });
    }
    return blob;
  }

  function kindFromFile(file) {
    var mime = guessMime(file);
    if (mime.indexOf("video/") === 0) return "video";
    if (VIDEO_EXT.test(file && file.name || "")) return "video";
    return "audio";
  }

  var rows = [];
  var player = {
    id: "",
    url: "",
    playing: false,
    muted: false,
    volume: 1
  };
  var wave = {
    peaks: [],
    duration: 0,
    sel0: -1,
    sel1: -1,
    dragging: false
  };
  var listen = {
    on: false,
    bits: []
  };
  var transcribeBusy = {};
  var liveRadio = {
    on: false,
    rec: null,
    stream: null,
    started: 0,
    busy: false
  };
  var searchQuery = "";

  var $ = function (id) {
    return document.getElementById(id);
  };

  function uid() {
    return "r" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatBytes(n) {
    var x = Number(n) || 0;
    if (x < 1024) return x + " B";
    if (x < 1024 * 1024) return (x / 1024).toFixed(1) + " KB";
    return (x / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatTime(sec) {
    var s = Math.max(0, Math.floor(Number(sec) || 0));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return m + ":" + (r < 10 ? "0" : "") + r;
  }

  function statusLabel(status) {
    if (status === "ready") return "Đã sẵn sàng";
    if (status === "heard") return "Đã nghe";
    return "Chưa sẵn sàng";
  }

  function lampClass(status) {
    if (status === "ready") return "lamp-ready";
    if (status === "heard") return "lamp-heard";
    return "lamp-pending";
  }

  function issueBadge(row) {
    var sum = row && row.analysis && row.analysis.summary;
    if (!sum) return "";
    if (!sum.issue_count) return " · REDA sạch";
    var bits = [];
    if (sum.red) bits.push("<span class=\"is-red\">" + sum.red + " RED</span>");
    if (sum.amber) bits.push("<span class=\"is-amber\">" + sum.amber + " AMBER</span>");
    return bits.length ? " · <span class=\"rec-badges\">" + bits.join(" ") + "</span>" : "";
  }

  function kindLabel(kind, type) {
    if (kind === "video") return "Video";
    if (kind === "audio") return "Ghi âm";
    if (String(type || "").indexOf("video/") === 0) return "Video";
    return "Ghi âm";
  }

  function showConvertModal(name) {
    var box = $("recConvertModal");
    var label = $("recConvertName");
    if (label) label.textContent = name || "";
    if (box) box.hidden = false;
    setConvertProgress(1, "Bắt đầu…");
  }

  function hideConvertModal() {
    var box = $("recConvertModal");
    if (box) box.hidden = true;
  }

  function setConvertProgress(percent, stage) {
    var pct = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    var bar = $("recConvertBar");
    var pctEl = $("recConvertPct");
    var stageEl = $("recConvertStage");
    if (bar) bar.style.width = pct + "%";
    if (pctEl) pctEl.textContent = pct + "%";
    if (stageEl) stageEl.textContent = stage || "";
  }

  var convertLocks = {};

  function transcodeOnServer(blob, name, onUploaded) {
    var key = String(name || "clip.avi") + ":" + String((blob && blob.size) || 0);
    if (convertLocks[key]) return convertLocks[key];
    showConvertModal(name);
    setConvertProgress(2, "Đang gửi file lên máy chủ…");
    var work = new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/media/transcode?name=" + encodeURIComponent(name || "clip.avi"));
      xhr.setRequestHeader("Content-Type", blob.type || "application/octet-stream");
      xhr.setRequestHeader("X-Filename", encodeURIComponent(name || "clip.avi"));
      xhr.upload.onprogress = function (ev) {
        if (!ev.lengthComputable) return;
        var pct = 2 + Math.round((ev.loaded / ev.total) * 10);
        setConvertProgress(
          pct,
          "Đang gửi file… " + formatBytes(ev.loaded) + " / " + formatBytes(ev.total)
        );
      };
      xhr.onerror = function () {
        hideConvertModal();
        reject(new Error("Không gửi được file convert."));
      };
      xhr.onload = function () {
        var payload = {};
        try {
          payload = JSON.parse(xhr.responseText || "{}");
        } catch (e) {
          hideConvertModal();
          reject(new Error("Máy chủ convert trả lời không hợp lệ."));
          return;
        }
        if (xhr.status >= 400 || !payload.ok || !payload.id) {
          hideConvertModal();
          reject(new Error(payload.error || "Không chuyển được AVI. Cần ffmpeg trên máy."));
          return;
        }
        if (typeof onUploaded === "function") {
          try {
            onUploaded();
          } catch (e) {}
        }
        pollConvertJob(payload.id, blob && blob.size, resolve, reject);
      };
      xhr.send(blob);
    });
    convertLocks[key] = work;
    work.then(
      function () {
        delete convertLocks[key];
      },
      function () {
        delete convertLocks[key];
      }
    );
    return work;
  }

  function pollConvertJob(jobId, size, resolve, reject) {
    var started = Date.now();
    var maxMs = 300000;
    function tick() {
      fetch("/api/media/transcode/status?id=" + encodeURIComponent(jobId), { cache: "no-store" })
        .then(function (res) {
          return res.json();
        })
        .then(function (job) {
          if (!job || job.ok === false && !job.id) {
            throw new Error((job && job.error) || "Mất tiến trình convert.");
          }
          var pct = 12 + Math.round((Number(job.percent) || 0) * 0.82);
          setConvertProgress(pct, job.stage || "Đang chuyển sang MP4…");
          if (job.error) throw new Error(job.error);
          if (job.done) {
            function download(attempt) {
              setConvertProgress(
                96,
                attempt ? "Kết nối bị ngắt, đang tải lại MP4…" : "Đang tải file để phát…"
              );
              return new Promise(function (got, fail) {
                var req = new XMLHttpRequest();
                req.open("GET", "/api/media/transcode/result?id=" + encodeURIComponent(jobId));
                req.responseType = "blob";
                req.onprogress = function (ev) {
                  if (!ev.lengthComputable) return;
                  setConvertProgress(
                    Math.min(99, 96 + Math.round((ev.loaded / ev.total) * 4)),
                    "Đang tải MP4… " + formatBytes(ev.loaded) + " / " + formatBytes(ev.total)
                  );
                };
                req.onload = function () {
                  if (req.status >= 400 || !req.response) {
                    fail(new Error("Không tải được file MP4."));
                    return;
                  }
                  var mime = (
                    req.getResponseHeader("Content-Type") ||
                    "video/mp4"
                  ).split(";")[0].trim();
                  setConvertProgress(100, "Xong.");
                  hideConvertModal();
                  got({
                    blob: req.response,
                    mime: mime,
                    duration: Number(job.duration) || 0
                  });
                };
                req.onerror = function () {
                  fail(new Error("Kết nối bị ngắt khi tải MP4."));
                };
                req.send();
              }).catch(function (err) {
                if (attempt >= 4) throw err;
                return new Promise(function (resume) {
                  setTimeout(resume, 1000 * (attempt + 1));
                }).then(function () {
                  return download(attempt + 1);
                });
              });
            }
            return download(0).then(resolve);
          }
          if (Date.now() - started > maxMs) throw new Error("Convert quá lâu.");
          setTimeout(tick, 300);
          return null;
        })
        .catch(function (err) {
          hideConvertModal();
          reject(err);
        });
    }
    tick();
  }

  function needsServerTranscode(name) {
    return extOf(name) === "avi";
  }

  function setTranscriptBox(text, interim) {
    var box = $("recTranscript");
    if (box && typeof text === "string") box.value = text;
    if ($("recInterim")) $("recInterim").textContent = interim || "";
  }

  function polishEn(text) {
    if (window.ATC && typeof ATC.repairHeard === "function") {
      return ATC.repairHeard(text, "en", { tape: true }).text || text;
    }
    return text;
  }

  function clock(sec) {
    return formatTime(sec);
  }

  function statusAfterAnalysis(row, cleaned) {
    if (!cleaned) return "Không nghe ra lời English trong file.";
    var sum = row.analysis && row.analysis.summary;
    if (!sum) return "Đã ghi lời English từ file.";
    if (sum.issue_count) {
      return (
        "Đã ghi lời English. REDA: " +
        (sum.red || 0) +
        " RED, " +
        (sum.amber || 0) +
        " AMBER."
      );
    }
    return "Đã ghi lời English. REDA: không bắt lỗi readback concept-level.";
  }

  function applyAnalysis(row, analysis) {
    if (!row || !analysis) return;
    row.analysis = analysis;
    row.turns = analysis.utterances || row.turns || [];
    row.minutesEn = analysis.minutes_en || "";
    row.scriptEn = analysis.script_en || "";
    if (analysis.transcript && !row.transcriptEn) row.transcriptEn = analysis.transcript;
    if (player.id === row.id || !player.id) {
      renderOps(row);
      renderTurns(row);
      renderIssues(row);
      setMinutes(row.minutesEn || "");
      setTranscriptBox(row.scriptEn || row.transcriptEn || analysis.transcript || "", "");
    }
  }

  function setMinutes(text) {
    var box = $("recMinutes");
    if (box) box.value = text || "";
  }

  function renderTurns(row) {
    var list = $("recTurns");
    if (!list) return;
    var turns = (row && (row.turns || (row.analysis && row.analysis.utterances))) || [];
    if (!turns.length) {
      list.innerHTML = "";
      return;
    }
    var q = searchQuery.toLowerCase();
    var clrByUtt = {};
    ((row.analysis && row.analysis.clearances) || []).forEach(function (c) {
      if (c.utterance_id) clrByUtt[c.utterance_id] = c;
      if (c.readback_utterance_id) clrByUtt[c.readback_utterance_id] = c;
    });
    list.innerHTML = turns
      .map(function (u) {
        var role = String(u.speaker_role || "UNKNOWN").toUpperCase();
        var roleClass = role === "ATCO" ? "is-atco" : role === "PILOT" ? "is-pilot" : "is-unknown";
        var stamp = u.t_clock || clock(u.t_start);
        var clr = clrByUtt[u.id] || {};
        var mark = clr.mark || "";
        var st = String(clr.status || "").toLowerCase();
        var hay = ((u.asr_text || "") + " " + (u.normalized || "") + " " + ((u.callsign && u.callsign.normalized) || "") + " " + (clr.status || "")).toLowerCase();
        var hidden = q && hay.indexOf(q) < 0 ? " is-hidden" : "";
        var norm = u.normalized && u.normalized !== (u.asr_text || "")
          ? "<span class=\"reda-norm\">" + escapeHtml(u.normalized) + (u.callsign && u.callsign.uncertain ? "  ? CALLSIGN UNCERTAIN" : "") + "</span>"
          : (u.callsign && u.callsign.uncertain ? "<span class=\"reda-norm\">? CALLSIGN UNCERTAIN</span>" : "");
        return (
          "<li class=\"" +
          hidden +
          "\" data-t=\"" +
          escapeHtml(String(u.t_start || 0)) +
          "\"><span class=\"reda-role " +
          roleClass +
          "\">" +
          escapeHtml(role) +
          "</span><span class=\"reda-line\">" +
          (mark ? "<span class=\"reda-mark is-" + escapeHtml(st) + "\">" + escapeHtml(mark) + "</span> " : "") +
          escapeHtml(u.asr_text || u.text || "") +
          norm +
          "</span><span class=\"clock\">" +
          escapeHtml(stamp) +
          "</span></li>"
        );
      })
      .join("");
  }

  function renderIssues(row) {
    var list = $("recIssues");
    var count = $("recIssueCount");
    var issues = (row && row.analysis && row.analysis.issues) || [];
    var sum = (row && row.analysis && row.analysis.summary) || {};
    if (count) {
      count.textContent = issues.length
        ? (sum.red || 0) + " RED · " + (sum.amber || 0) + " AMBER"
        : "Không có lỗi";
    }
    if (!list) return;
    if (!issues.length) {
      list.innerHTML = "<li class=\"rec-empty\">Chưa bắt lỗi readback. Nghe file hoặc dán lời English rồi Phân tích lại.</li>";
      return;
    }
    list.innerHTML = issues
      .map(function (iss) {
        var sev = String(iss.severity || "AMBER").toLowerCase();
        var icon = sev === "red" ? "!" : sev === "green" ? "✓" : "?";
        var title = icon + " " + (iss.severity || "") + " " + (iss.type || "") + (iss.field ? " · " + iss.field : "");
        var detail =
          "Expected " +
          (iss.expected || "—") +
          " · Got " +
          (iss.got || "—") +
          ". " +
          (iss.explanation_en || iss.teaching_en || "");
        return (
          "<li class=\"is-" +
          escapeHtml(sev) +
          "\" data-t=\"" +
          escapeHtml(String(iss.t_start || 0)) +
          "\"><span class=\"sev is-" +
          escapeHtml(sev) +
          "\">" +
          escapeHtml(iss.severity || "") +
          "</span><strong>" +
          escapeHtml(title) +
          "</strong><p>" +
          escapeHtml(detail) +
          "</p></li>"
        );
      })
      .join("");
  }

  function renderOps(row) {
    var air = $("recAircraft");
    var clr = $("recClearances");
    var count = $("recClrCount");
    var analysis = (row && row.analysis) || {};
    var aircraft = analysis.aircraft || [];
    var clearances = analysis.clearances || [];
    if (count) {
      var s = analysis.summary || {};
      count.textContent = clearances.length
        ? (s.matched || 0) + " ✓ · " + (s.mismatch || 0) + " ! · " + (s.missing || 0) + " …"
        : "—";
    }
    if (air) {
      air.innerHTML = aircraft.length
        ? aircraft
            .map(function (a) {
              return (
                "<li data-cs=\"" +
                escapeHtml(a.callsign || "") +
                "\"><strong>" +
                escapeHtml(a.callsign || "?") +
                "</strong>" +
                (a.uncertain ? " <span class=\"reda-mark is-uncertain\">?</span>" : "") +
                (a.spoken ? "<span class=\"reda-norm\">" + escapeHtml(a.spoken) + "</span>" : "") +
                "</li>"
              );
            })
            .join("")
        : "<li class=\"rec-empty\">Chưa nhận callsign.</li>";
    }
    if (clr) {
      clr.innerHTML = clearances.length
        ? clearances
            .map(function (c) {
              var cmds = (c.commands || [])
                .map(function (x) {
                  return (x.action || "") + " " + (x.label || x.value || "");
                })
                .join(" · ");
              var st = String(c.status || "").toLowerCase();
              return (
                "<li data-t=\"" +
                escapeHtml(String(c.t_start || 0)) +
                "\"><span class=\"reda-mark is-" +
                escapeHtml(st) +
                "\">" +
                escapeHtml(c.mark || "") +
                "</span><strong>" +
                escapeHtml(c.callsign || "?") +
                "</strong> " +
                escapeHtml(c.status || "") +
                " · " +
                escapeHtml(cmds) +
                "</li>"
              );
            })
            .join("")
        : "<li class=\"rec-empty\">Chưa có clearance.</li>";
    }
  }

  function showRowAnalysis(row) {
    renderOps(row);
    renderTurns(row);
    renderIssues(row);
    setMinutes((row && row.minutesEn) || "");
    if (row && (row.scriptEn || row.transcriptEn)) {
      setTranscriptBox(row.scriptEn || row.transcriptEn, "");
    }
  }

  function seekTo(sec) {
    var id = player.id || playableRowId();
    var row = id ? findRow(id) : null;
    if (row) bindVideo(row);
    var video = $("recVideo");
    if (!video || !player.url) return;
    try {
      video.currentTime = Math.max(0, Number(sec) || 0);
    } catch (e) {}
    refreshNow();
  }

  function analyzeRow(row) {
    if (!row) return Promise.resolve();
    var body = {
      filename: row.name || "",
      text: row.transcriptEn || ($("recTranscript") && $("recTranscript").value) || "",
      turns: row.turns || []
    };
    return fetch("/api/reda/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (analysis) {
        if (!analysis || analysis.ok === false) {
          throw new Error((analysis && analysis.error) || "Không phân tích được readback.");
        }
        applyAnalysis(row, analysis);
        if (analysis.session_id && body.text && analysis.transcript && body.text.trim() !== analysis.transcript.trim()) {
          fetch("/api/reda/correction", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: analysis.session_id,
              utterance_id: (analysis.utterances && analysis.utterances[0] && analysis.utterances[0].id) || "",
              before: analysis.transcript,
              after: body.text,
              reason: "transcript edit"
            })
          }).catch(function () {});
        }
        return putRow(row).then(function () {
          render();
          return analysis;
        });
      });
  }

  function transcribeOnServer(blob, name, onPartial) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/media/transcribe?name=" + encodeURIComponent(name || "clip.mp4"));
      xhr.setRequestHeader("Content-Type", blob.type || "application/octet-stream");
      xhr.setRequestHeader("X-Filename", encodeURIComponent(name || "clip.mp4"));
      xhr.onerror = function () {
        reject(new Error("Không gửi được file để ghi lời."));
      };
      xhr.onload = function () {
        var payload = {};
        try {
          payload = JSON.parse(xhr.responseText || "{}");
        } catch (e) {
          reject(new Error("Máy chủ ghi lời trả lời không hợp lệ."));
          return;
        }
        if (xhr.status >= 400 || !payload.ok || !payload.id) {
          reject(new Error(payload.error || "Không ghi được lời English từ file."));
          return;
        }
        pollTranscribeJob(payload.id, onPartial, resolve, reject);
      };
      xhr.send(blob);
    });
  }

  function pollTranscribeJob(jobId, onPartial, resolve, reject) {
    var tries = 0;
    function tick() {
      fetch("/api/media/transcribe/status?id=" + encodeURIComponent(jobId), { cache: "no-store" })
        .then(function (res) {
          return res.json();
        })
        .then(function (job) {
          if (!job || (job.ok === false && !job.id)) {
            throw new Error((job && job.error) || "Mất tiến trình ghi lời.");
          }
          if (job.text && onPartial) onPartial(job.text, job.stage);
          if (job.error) throw new Error(job.error);
          if (job.done) {
            resolve({
              text: job.text || "",
              turns: job.turns || [],
              analysis: job.analysis || null
            });
            return;
          }
          tries += 1;
          if (tries > 1800) throw new Error("Ghi lời quá lâu.");
          setTimeout(tick, 400);
          return null;
        })
        .catch(reject);
    }
    tick();
  }

  function startFileTranscript(row) {
    if (!row || !row.blob) return;
    if (row.transcriptEn) {
      setTranscriptBox(row.transcriptEn, "");
      return;
    }
    if (transcribeBusy[row.id]) return;
    transcribeBusy[row.id] = true;
    setStatus("Đang ghi lời English từ file…", "live");
    transcribeOnServer(row.blob, row.name, function (partial, stage) {
      if (player.id === row.id || !player.id) {
        setTranscriptBox(partial, stage || "đang ghi…");
      }
    })
      .then(function (payload) {
        var text = typeof payload === "string" ? payload : (payload && payload.text) || "";
        var cleaned = polishEn(text);
        row.transcriptEn = cleaned;
        row.turns = (payload && payload.turns) || row.turns || [];
        if (player.id === row.id || !player.id) setTranscriptBox(cleaned, "");
        var next = payload && payload.analysis
          ? Promise.resolve(applyAnalysis(row, payload.analysis))
          : cleaned
            ? analyzeRow(row)
            : Promise.resolve();
        return next.then(function () {
          return putRow(row);
        }).then(function () {
          render();
          setStatus(statusAfterAnalysis(row, cleaned), cleaned ? "ok" : "warn");
        });
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Không ghi được lời từ file.", "warn");
      })
      .then(function () {
        delete transcribeBusy[row.id];
      });
  }

  function prepareRow(row) {
    function applyConverted(out) {
      row.blob = out.blob;
      row.type = out.mime || out.blob.type || "video/mp4";
      row.kind = String(row.type).indexOf("audio/") === 0 ? "audio" : "video";
      row.size = out.blob.size || row.size;
      if (out.duration > 0) {
        return { ok: true, kind: row.kind, duration: out.duration, error: "" };
      }
      return probeBlob(row.blob, row.name);
    }
    function dropSourceBlob() {
      row.blob = null;
    }
    var start = needsServerTranscode(row.name)
      ? transcodeOnServer(row.blob, row.name, dropSourceBlob).then(applyConverted)
      : probeBlob(row.blob, row.name).then(function (info) {
          if (info.ok) return info;
          var ext = extOf(row.name);
          if (ext !== "mkv" && ext !== "mov") return info;
          setStatus("Đang chuyển “" + row.name + "” để phát được…", "live");
          return transcodeOnServer(row.blob, row.name, dropSourceBlob).then(applyConverted);
        });
    return start;
  }

  function isMediaFile(file) {
    var type = String(file && file.type || "").toLowerCase();
    if (type.indexOf("audio/") === 0 || type.indexOf("video/") === 0) return true;
    if (type === "application/x-troff-msvideo") return true;
    return ACCEPT_EXT.test(file && file.name || "");
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: "id" });
        }
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
      req.onerror = function () {
        reject(req.error);
      };
    });
  }

  function withStore(mode, fn) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, mode);
        var store = tx.objectStore(STORE);
        var req = fn(store);
        tx.oncomplete = function () {
          resolve(req && "result" in req ? req.result : undefined);
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function listRows() {
    return withStore("readonly", function (store) {
      return store.getAll();
    }).then(function (list) {
      return (list || []).sort(function (a, b) {
        return (b.addedAt || 0) - (a.addedAt || 0);
      });
    });
  }

  function putRow(row) {
    return withStore("readwrite", function (store) {
      store.put(rowForStore(row));
    });
  }

  function rowForStore(row) {
    if (!row || !row.blob || row.blob.size < 32 * 1024 * 1024) return row;
    if (row.status === "ready" || row.status === "heard") return row;
    var slim = {};
    Object.keys(row).forEach(function (key) {
      slim[key] = row[key];
    });
    slim.blob = null;
    return slim;
  }

  function deleteRow(id) {
    return withStore("readwrite", function (store) {
      store.delete(id);
    });
  }

  function findRow(id) {
    var i;
    for (i = 0; i < rows.length; i++) {
      if (rows[i].id === id) return rows[i];
    }
    return null;
  }

  function setStatus(msg, kind) {
    var el = $("recStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "status " + (kind || "");
  }

  function hasAudioTrack(el) {
    if (!el) return true;
    if (el.mozHasAudio === false) return false;
    if (el.audioTracks && typeof el.audioTracks.length === "number") {
      return el.audioTracks.length > 0;
    }
    return true;
  }

  function probeBlob(blob, name) {
    return new Promise(function (resolve) {
      var mime = guessMime({ name: name || blob && blob.name, type: blob && blob.type });
      var media = playableBlob(blob, mime);
      var el = document.createElement("video");
      el.preload = "metadata";
      el.muted = true;
      el.playsInline = true;
      var url = URL.createObjectURL(media);
      var settled = false;
      function done(result) {
        if (settled) return;
        settled = true;
        el.onloadedmetadata = null;
        el.onerror = null;
        try {
          el.removeAttribute("src");
          el.load();
        } catch (e) {}
        try {
          URL.revokeObjectURL(url);
        } catch (e2) {}
        resolve(result);
      }
      var timer = setTimeout(function () {
        done({
          ok: false,
          kind: mime.indexOf("video/") === 0 || VIDEO_EXT.test(name || "") ? "video" : "audio",
          duration: 0,
          error: "Không đọc được metadata"
        });
      }, 12000);
      el.onloadedmetadata = function () {
        clearTimeout(timer);
        var kind = el.videoWidth > 0 || mime.indexOf("video/") === 0 || VIDEO_EXT.test(name || "") ? "video" : "audio";
        var duration = isFinite(el.duration) ? el.duration : 0;
        var audio = hasAudioTrack(el);
        done({
          ok: audio,
          kind: kind,
          duration: duration,
          error: audio ? "" : "Không thấy kênh âm thanh"
        });
      };
      el.onerror = function () {
        clearTimeout(timer);
        var avi = extOf(name || "") === "avi" || mime === "video/x-msvideo";
        done({
          ok: false,
          kind: mime.indexOf("video/") === 0 || VIDEO_EXT.test(name || "") ? "video" : "audio",
          duration: 0,
          error: avi
            ? "Trình duyệt không giải mã được codec trong file AVI này. Thử Edge hoặc chuyển sang mp4."
            : "Máy không phát được định dạng này"
        });
      };
      if (mime) {
        while (el.firstChild) el.removeChild(el.firstChild);
        var source = document.createElement("source");
        source.src = url;
        source.type = mime;
        el.appendChild(source);
        if (mime === "video/x-msvideo") {
          var alt = document.createElement("source");
          alt.src = url;
          alt.type = "video/avi";
          el.appendChild(alt);
        }
        el.load();
      } else {
        el.src = url;
      }
    });
  }

  function render() {
    var list = $("recList");
    if (!list) return;
    if (!rows.length) {
      list.innerHTML = "<li class=\"rec-empty\">Chưa có bản ghi. Import file ghi âm hoặc video có tiếng.</li>";
      return;
    }
    list.innerHTML = rows
      .map(function (row) {
        var on = player.id === row.id;
        var canPlay = row.status === "ready" || row.status === "heard";
        var note = row.error && row.status === "pending" ? " · " + escapeHtml(row.error) : "";
        return (
          "<li class=\"rec-item" +
          (on ? " is-current" : "") +
          "\" data-id=\"" +
          escapeHtml(row.id) +
          "\">" +
          "<span class=\"rec-lamp " +
          lampClass(row.status) +
          "\" title=\"" +
          escapeHtml(statusLabel(row.status)) +
          "\" aria-label=\"" +
          escapeHtml(statusLabel(row.status)) +
          "\"></span>" +
          "<div class=\"rec-meta\">" +
          "<strong>" +
          escapeHtml(row.name) +
          "</strong>" +
          "<span class=\"meta\">" +
          escapeHtml(kindLabel(row.kind, row.type)) +
          " · " +
          (row.duration ? formatTime(row.duration) : "—:—") +
          " · " +
          formatBytes(row.size) +
          " · " +
          escapeHtml(statusLabel(row.status)) +
          note +
          issueBadge(row) +
          "</span></div>" +
          "<div class=\"rec-transport\">" +
          "<button type=\"button\" data-act=\"play\"" +
          (canPlay ? "" : " disabled") +
          (on && player.playing ? " class=\"is-active en\"" : "") +
          ">Phát</button>" +
          "<button type=\"button\" data-act=\"pause\"" +
          (canPlay ? "" : " disabled") +
          ">Tạm dừng</button>" +
          "<button type=\"button\" data-act=\"stop\"" +
          (canPlay ? "" : " disabled") +
          ">Stop</button>" +
          "<button type=\"button\" class=\"ghost\" data-act=\"delete\">Xóa</button>" +
          "</div></li>"
        );
      })
      .join("");
  }

  function applySpeakerUi() {
    var btn = $("btnRecSpeaker");
    var slash = btn && btn.querySelector(".rec-speaker-slash");
    var on = !player.muted;
    if (btn) {
      btn.classList.toggle("is-off", !on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.setAttribute("title", on ? "Tắt loa" : "Bật loa");
      btn.setAttribute("aria-label", on ? "Tắt loa" : "Bật loa");
    }
    if (slash) slash.hidden = on;
  }

  function applyVolume() {
    var video = $("recVideo");
    if (video) {
      video.muted = !!player.muted;
      video.volume = Math.max(0, Math.min(1, player.volume));
    }
    applySpeakerUi();
  }

  function toggleSpeaker() {
    player.muted = !player.muted;
    applyVolume();
  }

  function drawWave() {
    var canvas = $("recWave");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.clientWidth || 640;
    var h = canvas.height || 80;
    if (canvas.width !== w) canvas.width = w;
    ctx.fillStyle = "#041018";
    ctx.fillRect(0, 0, w, h);
    var peaks = wave.peaks || [];
    var n = peaks.length;
    if (!n) {
      ctx.fillStyle = "#1c3344";
      ctx.fillRect(0, h / 2 - 1, w, 2);
      return;
    }
    var video = $("recVideo");
    var dur = wave.duration || (video && video.duration) || 0;
    var cur = video && player.url ? video.currentTime || 0 : 0;
    var s0 = Math.min(wave.sel0, wave.sel1);
    var s1 = Math.max(wave.sel0, wave.sel1);
    if (s1 > s0 && dur > 0) {
      ctx.fillStyle = "rgba(62, 199, 184, 0.18)";
      ctx.fillRect((s0 / dur) * w, 0, ((s1 - s0) / dur) * w, h);
    }
    var mid = h / 2;
    var gap = w / n;
    ctx.fillStyle = "#3ec7b8";
    var i;
    for (i = 0; i < n; i++) {
      var amp = Math.max(1, peaks[i] * (mid - 2));
      ctx.fillRect(i * gap, mid - amp, Math.max(1, gap - 0.4), amp * 2);
    }
    if (dur > 0) {
      var x = (cur / dur) * w;
      ctx.strokeStyle = "#ffd27a";
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
  }

  function loadWaveform(row) {
    wave.peaks = [];
    wave.duration = row && row.duration ? row.duration : 0;
    wave.sel0 = -1;
    wave.sel1 = -1;
    drawWave();
    if (!row || !row.blob || !window.AudioContext && !window.webkitAudioContext) return;
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    row.blob
      .arrayBuffer()
      .then(function (buf) {
        return ctx.decodeAudioData(buf);
      })
      .then(function (audio) {
        if (!player.id || player.id !== row.id) return;
        var ch0 = audio.getChannelData(0);
        var ch1 = audio.numberOfChannels > 1 ? audio.getChannelData(1) : null;
        var bins = Math.min(900, Math.max(180, Math.floor((canvasWidth() || 640) * 1.2)));
        var step = Math.max(1, Math.floor(ch0.length / bins));
        var peaks = [];
        var i;
        for (i = 0; i < bins; i++) {
          var a = i * step;
          var b = Math.min(ch0.length, a + step);
          var peak = 0;
          var j;
          for (j = a; j < b; j += 8) {
            var s = Math.abs(ch0[j]);
            if (ch1) s = Math.max(s, Math.abs(ch1[j]));
            if (s > peak) peak = s;
          }
          peaks.push(peak);
        }
        wave.peaks = peaks;
        wave.duration = audio.duration || row.duration || 0;
        drawWave();
        try {
          ctx.close();
        } catch (e) {}
      })
      .catch(function () {
        drawWave();
      });
  }

  function canvasWidth() {
    var canvas = $("recWave");
    return canvas ? canvas.clientWidth : 0;
  }

  function timeFromWaveX(clientX) {
    var canvas = $("recWave");
    if (!canvas) return 0;
    var rect = canvas.getBoundingClientRect();
    var x = Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width)));
    var dur = wave.duration || 0;
    var video = $("recVideo");
    if ((!dur || !isFinite(dur)) && video && isFinite(video.duration)) dur = video.duration;
    return x * dur;
  }

  function refreshNow() {
    var video = $("recVideo");
    var name = $("recNowName");
    var time = $("recNowTime");
    var bar = $("recFileBar");
    var waveWrap = $("recWaveWrap");
    var wrap = document.querySelector(".rec-video-wrap");
    var row = findRow(player.id);
    if (!video) return;
    if (!row || !player.url) {
      if (bar) bar.hidden = true;
      if (waveWrap) waveWrap.hidden = true;
      if (wrap) wrap.classList.remove("has-media");
      video.classList.remove("is-video");
      if (name) name.textContent = "Chưa có file";
      if (time) time.textContent = "0:00 / 0:00";
      drawWave();
      return;
    }
    if (bar) bar.hidden = false;
    if (waveWrap) waveWrap.hidden = false;
    if (wrap) wrap.classList.add("has-media");
    if (name) name.textContent = row.name;
    var cur = video.currentTime || 0;
    var dur = isFinite(video.duration) && video.duration > 0 ? video.duration : row.duration || wave.duration || 0;
    if (time) time.textContent = formatTime(cur) + " / " + formatTime(dur);
    var showVideo = row.kind === "video" || video.videoWidth > 0;
    video.classList.toggle("is-video", showVideo);
    if (wave.sel1 > wave.sel0 && dur > 0 && cur >= wave.sel1 - 0.04) {
      try {
        video.currentTime = wave.sel0;
      } catch (e) {}
    }
    applyVolume();
    drawWave();
  }

  function detachPlayer() {
    var video = $("recVideo");
    if (video) {
      try {
        video.pause();
        video.onended = null;
        video.ontimeupdate = null;
        video.onloadedmetadata = null;
        video.onerror = null;
        video.removeAttribute("src");
        while (video.firstChild) video.removeChild(video.firstChild);
        video.load();
      } catch (e) {}
    }
    if (player.url) {
      try {
        URL.revokeObjectURL(player.url);
      } catch (e2) {}
    }
    player.id = "";
    player.url = "";
    player.playing = false;
    wave.peaks = [];
    wave.duration = 0;
    wave.sel0 = -1;
    wave.sel1 = -1;
    stopRecListen(true);
    refreshNow();
  }

  function markHeard(id) {
    var row = findRow(id);
    if (!row || row.status === "heard") return Promise.resolve();
    row.status = "heard";
    render();
    return putRow(row);
  }

  function bindVideo(row) {
    var video = $("recVideo");
    if (!video) return null;
    if (player.id === row.id && player.url) return video;
    detachPlayer();
    var mime = guessMime({ name: row.name, type: row.type || (row.blob && row.blob.type) });
    var media = playableBlob(row.blob, mime);
    var url = URL.createObjectURL(media);
    player.id = row.id;
    player.url = url;
    while (video.firstChild) video.removeChild(video.firstChild);
    video.removeAttribute("src");
    if (mime) {
      var source = document.createElement("source");
      source.src = url;
      source.type = mime;
      video.appendChild(source);
      if (mime === "video/x-msvideo") {
        var alt = document.createElement("source");
        alt.src = url;
        alt.type = "video/avi";
        video.appendChild(alt);
      }
    } else {
      video.src = url;
    }
    video.load();
    video.ontimeupdate = function () {
      refreshNow();
      var dur = video.duration;
      if (isFinite(dur) && dur > 8 && video.currentTime / dur >= 0.92) {
        markHeard(row.id);
      }
    };
    video.onended = function () {
      player.playing = false;
      stopRecListen(true);
      markHeard(row.id).then(render);
      refreshNow();
      setStatus("Hết “" + row.name + "”. Đã nghe.", "ok");
    };
    video.onerror = function () {
      player.playing = false;
      setStatus("Không phát được “" + row.name + "”.", "warn");
      render();
    };
    video.onloadedmetadata = function () {
      if (row.kind !== "video" && video.videoWidth > 0) {
        row.kind = "video";
      }
      if (isFinite(video.duration) && video.duration > 0) {
        wave.duration = video.duration;
      }
      refreshNow();
    };
    applyVolume();
    loadWaveform(row);
    showRowAnalysis(row);
    refreshNow();
    render();
    return video;
  }

  function playRow(id) {
    var row = findRow(id);
    if (!row || (row.status !== "ready" && row.status !== "heard")) {
      setStatus("File chưa sẵn sàng để phát.", "warn");
      return;
    }
    var video = bindVideo(row);
    if (!video) return;
    var rateEl = $("recTapeRate");
    var rate = Number(rateEl && rateEl.value ? rateEl.value : 0.85);
    if (isFinite(rate) && rate > 0) {
      video.playbackRate = Math.max(0.5, Math.min(1.25, rate));
      if ("preservesPitch" in video) video.preservesPitch = true;
    }
    var play = video.play();
    player.playing = true;
    render();
    refreshNow();
    if (play && play.catch) {
      play.catch(function () {
        player.playing = false;
        setStatus("Trình duyệt chặn phát. Bấm Phát lại.", "warn");
        render();
      });
    }
    setStatus("Đang phát “" + row.name + "”.", "live");
    startFileTranscript(row);
  }

  function pauseRow(id) {
    var video = $("recVideo");
    if (!video || player.id !== id) return;
    video.pause();
    player.playing = false;
    render();
    setStatus("Đã tạm dừng.", "");
  }

  function stopRow(id) {
    var video = $("recVideo");
    if (!video || (id && player.id !== id)) return;
    try {
      video.pause();
      video.currentTime = 0;
    } catch (e) {}
    player.playing = false;
    render();
    refreshNow();
    setStatus("Đã dừng.", "");
  }

  function importFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []).filter(Boolean);
    if (!files.length) return;
    var skipped = 0;
    var accepted = files.filter(function (f) {
      if (!isMediaFile(f)) {
        skipped += 1;
        return false;
      }
      return true;
    });
    if (!accepted.length) {
      setStatus("Không có file ghi âm / video hợp lệ.", "warn");
      return;
    }
    setStatus("Đang kiểm tra " + accepted.length + " file…", "live");
    var chain = Promise.resolve();
    accepted.forEach(function (file) {
      chain = chain.then(function () {
        var row = {
          id: uid(),
          name: file.name || "bản ghi",
          type: guessMime(file),
          size: file.size || 0,
          addedAt: Date.now(),
          duration: 0,
          status: "pending",
          kind: kindFromFile(file),
          error: "",
          blob: needsServerTranscode(file.name) ? file : playableBlob(file, guessMime(file))
        };
        rows.unshift(row);
        render();
        if (needsServerTranscode(row.name)) {
          setStatus("Đang chuyển AVI sang MP4 để phát…", "live");
        }
        return putRow(row)
          .then(function () {
            return prepareRow(row);
          })
          .then(function (info) {
            row.kind = info.kind || row.kind;
            row.duration = info.duration || 0;
            row.error = info.error || "";
            row.status = info.ok ? "ready" : "pending";
            render();
            if (info.ok && (!player.id || player.id === row.id)) {
              bindVideo(row);
            }
            return putRow(row);
          })
          .catch(function (err) {
            row.error = (err && err.message) || "Không chuyển được file";
            row.status = "pending";
            render();
            return putRow(row);
          });
      });
    });
    chain
      .then(function () {
        var ready = rows.filter(function (r) {
          return r.status === "ready" || r.status === "heard";
        }).length;
        var msg = "Đã import " + accepted.length + " file. " + ready + " sẵn sàng.";
        if (skipped) msg += " Bỏ qua " + skipped + " file không phải âm thanh/video.";
        setStatus(msg, "ok");
      })
      .catch(function () {
        setStatus("Không lưu được bản ghi trên máy này.", "warn");
      });
  }

  function loadList() {
    return listRows()
      .then(function (list) {
        rows = list || [];
        render();
        var pending = rows.filter(function (r) {
          return r.status === "pending" && r.blob;
        });
        pending.forEach(function (row) {
          var work = needsServerTranscode(row.name)
            ? prepareRow(row)
            : probeBlob(row.blob, row.name);
          work
            .then(function (info) {
              row.kind = info.kind || row.kind;
              row.duration = info.duration || 0;
              row.error = info.error || "";
              row.status = info.ok ? "ready" : "pending";
              render();
              putRow(row);
            })
            .catch(function (err) {
              row.error = (err && err.message) || "Không chuyển được file";
              render();
              putRow(row);
            });
        });
        if (!rows.length) setStatus("Sẵn sàng import bản ghi.", "");
      })
      .catch(function () {
        setStatus("Không mở được kho bản ghi trên máy này.", "warn");
        render();
      });
  }

  function speechApi() {
    return window.ATC && ATC.speech;
  }

  function updateListenButtons() {
    var btn = $("btnRecListen");
    var dot = $("recLiveDot");
    if (btn) btn.classList.toggle("is-active", !!listen.on);
    if (dot) dot.classList.toggle("is-on", !!listen.on);
  }

  function stopLiveRadio(quiet) {
    liveRadio.on = false;
    try {
      if (liveRadio.rec && liveRadio.rec.state !== "inactive") liveRadio.rec.stop();
    } catch (e) {}
    liveRadio.rec = null;
    if (liveRadio.stream) {
      liveRadio.stream.getTracks().forEach(function (t) {
        t.stop();
      });
    }
    liveRadio.stream = null;
    var btn = $("btnRecLive");
    if (btn) btn.classList.remove("btn-live-on");
    if (!quiet) setStatus("Đã dừng LIVE radio.", "");
  }

  function ensureLiveRow() {
    var i;
    for (i = 0; i < rows.length; i++) {
      if (rows[i].live) return rows[i];
    }
    var row = {
      id: uid(),
      name: "LIVE-radio.webm",
      kind: "audio",
      status: "ready",
      live: true,
      addedAt: Date.now(),
      turns: [],
      transcriptEn: "",
      blob: new Blob([], { type: "audio/webm" })
    };
    rows.unshift(row);
    putRow(row);
    render();
    return row;
  }

  function ingestLiveChunk(blob) {
    if (!blob || !blob.size || liveRadio.busy) return;
    liveRadio.busy = true;
    var row = ensureLiveRow();
    var offset = (Date.now() - liveRadio.started) / 1000;
    transcribeOnServer(blob, "live-" + Math.floor(offset) + ".webm", function (partial) {
      if ($("recInterim")) $("recInterim").textContent = partial || "";
    })
      .then(function (payload) {
        var extra = (payload && payload.turns) || [];
        extra.forEach(function (t) {
          t.t_start = (Number(t.t_start) || 0) + Math.max(0, offset - 8);
          t.t_end = (Number(t.t_end) || t.t_start) + Math.max(0, offset - 8);
        });
        row.turns = (row.turns || []).concat(extra);
        var text = typeof payload === "string" ? payload : (payload && payload.text) || "";
        if (text) {
          row.transcriptEn = ((row.transcriptEn || "") + "\n" + text).trim();
        }
        player.id = row.id;
        return analyzeRow(row);
      })
      .then(function () {
        setStatus("LIVE: đã ghi đoạn radio.", "live");
      })
      .catch(function (err) {
        setStatus((err && err.message) || "LIVE không ghi được đoạn này.", "warn");
      })
      .then(function () {
        liveRadio.busy = false;
      });
  }

  function startLiveRadio() {
    if (liveRadio.on) {
      stopLiveRadio();
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Trình duyệt không cho phép LIVE radio.", "warn");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          channelCount: 1
        }
      })
      .then(function (stream) {
        liveRadio.stream = stream;
        liveRadio.started = Date.now();
        liveRadio.on = true;
        var mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        var rec = new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 64000 });
        liveRadio.rec = rec;
        rec.ondataavailable = function (ev) {
          if (ev.data && ev.data.size > 800) ingestLiveChunk(ev.data);
        };
        rec.start(7000);
        ensureLiveRow();
        var btn = $("btnRecLive");
        if (btn) btn.classList.add("btn-live-on");
        listen.on = true;
        updateListenButtons();
        setStatus("LIVE radio: line-in / micro (tắt echo). Đoạn ~7s, overlap 1.5s trên máy.", "live");
      })
      .catch(function (err) {
        setStatus((err && err.message) || "Không mở được micro / line-in.", "warn");
      });
  }

  function stopRecListen(quiet) {
    var speech = speechApi();
    if (speech && speech.listening) {
      speech.stop({ keepTape: true });
    }
    if (liveRadio.on) stopLiveRadio(true);
    listen.on = false;
    updateListenButtons();
    if ($("recInterim")) $("recInterim").textContent = "";
    if (!quiet) setStatus("Đã dừng nghe.", "");
  }

  function playableRowId() {
    if (player.id && findRow(player.id)) return player.id;
    var i;
    for (i = 0; i < rows.length; i++) {
      if (rows[i].status === "ready" || rows[i].status === "heard") return rows[i].id;
    }
    return "";
  }

  function startRecListen() {
    if (listen.on) {
      stopRecListen();
      return;
    }
    var id = playableRowId();
    if (!id) {
      setStatus("Import bản ghi rồi bấm Phát hoặc NGHE (EN).", "warn");
      return;
    }
    playRow(id);
    var row = findRow(id);
    if (row) startFileTranscript(row);
    listen.on = true;
    updateListenButtons();
    setStatus("Đang ghi lời English trực tiếp từ file (không cần micro).", "live");
  }

  function bindUi() {
    var drop = $("recDrop");
    var input = $("recFile");
    var btn = $("btnRecImport");
    var list = $("recList");
    var listenBtn = $("btnRecListen");
    var liveBtn = $("btnRecLive");
    var listenStop = $("btnRecListenStop");
    var copyEn = $("copyRecEn");
    var copyMin = $("copyRecMinutes");
    var analyzeBtn = $("btnRecAnalyze");
    var toHall = $("btnRecToHall");
    var turns = $("recTurns");
    var issues = $("recIssues");

    if (btn && input) {
      btn.addEventListener("click", function () {
        input.click();
      });
    }
    if (input) {
      input.addEventListener("change", function () {
        importFiles(this.files);
        this.value = "";
      });
    }
    if (drop) {
      ["dragenter", "dragover"].forEach(function (ev) {
        drop.addEventListener(ev, function (e) {
          e.preventDefault();
          drop.classList.add("is-over");
        });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        drop.addEventListener(ev, function () {
          drop.classList.remove("is-over");
        });
      });
      drop.addEventListener("drop", function (e) {
        e.preventDefault();
        importFiles(e.dataTransfer && e.dataTransfer.files);
      });
      drop.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (input) input.click();
        }
      });
    }
    if (list) {
      list.addEventListener("click", function (e) {
        var btnEl = e.target.closest("button[data-act]");
        var item = e.target.closest("[data-id]");
        if (!item) return;
        var id = item.getAttribute("data-id");
        if (!btnEl) {
          var row = findRow(id);
          if (row && (row.status === "ready" || row.status === "heard")) bindVideo(row);
          return;
        }
        var act = btnEl.getAttribute("data-act");
        if (act === "play") playRow(id);
        else if (act === "pause") pauseRow(id);
        else if (act === "stop") stopRow(id);
        else if (act === "delete") {
          if (!window.confirm("Xóa bản ghi này khỏi máy?")) return;
          if (player.id === id) detachPlayer();
          rows = rows.filter(function (r) {
            return r.id !== id;
          });
          render();
          deleteRow(id).then(function () {
            setStatus("Đã xóa bản ghi.", "ok");
          });
        }
      });
    }
    var speaker = $("btnRecSpeaker");
    if (speaker) {
      speaker.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleSpeaker();
      });
    }
    if ($("btnRecPlay")) {
      $("btnRecPlay").addEventListener("click", function () {
        var id = playableRowId();
        if (id) playRow(id);
      });
    }
    if ($("btnRecPause")) {
      $("btnRecPause").addEventListener("click", function () {
        if (player.id) pauseRow(player.id);
      });
    }
    if ($("btnRecStop")) {
      $("btnRecStop").addEventListener("click", function () {
        if (player.id) stopRow(player.id);
      });
    }
    if ($("recVol")) {
      $("recVol").addEventListener("input", function () {
        player.volume = Math.max(0, Math.min(1, Number(this.value) / 100));
        if (player.volume > 0 && player.muted) player.muted = false;
        applyVolume();
      });
    }
    if ($("btnRecDelete")) {
      $("btnRecDelete").addEventListener("click", function () {
        var id = player.id;
        if (!id) return;
        if (!window.confirm("Xóa bản ghi này khỏi máy?")) return;
        detachPlayer();
        rows = rows.filter(function (r) {
          return r.id !== id;
        });
        render();
        deleteRow(id).then(function () {
          setStatus("Đã xóa bản ghi.", "ok");
        });
      });
    }
    var canvas = $("recWave");
    if (canvas) {
      canvas.addEventListener("pointerdown", function (e) {
        if (!player.url) return;
        canvas.setPointerCapture(e.pointerId);
        wave.dragging = true;
        var t = timeFromWaveX(e.clientX);
        wave.sel0 = t;
        wave.sel1 = t;
        var video = $("recVideo");
        if (video) {
          try {
            video.currentTime = t;
          } catch (err) {}
        }
        drawWave();
      });
      canvas.addEventListener("pointermove", function (e) {
        if (!wave.dragging) return;
        wave.sel1 = timeFromWaveX(e.clientX);
        drawWave();
      });
      function endWaveDrag(e) {
        if (!wave.dragging) return;
        wave.dragging = false;
        wave.sel1 = timeFromWaveX(e.clientX);
        if (Math.abs(wave.sel1 - wave.sel0) < 0.25) {
          wave.sel0 = -1;
          wave.sel1 = -1;
        }
        drawWave();
      }
      canvas.addEventListener("pointerup", endWaveDrag);
      canvas.addEventListener("pointercancel", endWaveDrag);
    }
    window.addEventListener("resize", function () {
      drawWave();
    });
    applySpeakerUi();
    if (listenBtn) {
      listenBtn.addEventListener("click", startRecListen);
    }
    if (liveBtn) {
      liveBtn.addEventListener("click", startLiveRadio);
    }
    if (listenStop) {
      listenStop.addEventListener("click", function () {
        stopRecListen();
      });
    }
    if ($("recSearch")) {
      $("recSearch").addEventListener("input", function () {
        searchQuery = String(this.value || "").trim();
        var id = player.id || playableRowId();
        var row = id ? findRow(id) : rows[0];
        renderTurns(row);
        if (searchQuery.length >= 2) {
          fetch("/api/reda/search?q=" + encodeURIComponent(searchQuery), { cache: "no-store" })
            .then(function (res) {
              return res.json();
            })
            .then(function (payload) {
              if (!payload || !payload.hits) return;
              var n = payload.hits.length;
              if (n) setStatus("Kho phiên: " + n + " lượt khớp “" + searchQuery + "”.", "");
            })
            .catch(function () {});
        }
      });
    }
    if ($("recAircraft")) {
      $("recAircraft").addEventListener("click", function (e) {
        var item = e.target.closest("[data-cs]");
        if (!item) return;
        searchQuery = item.getAttribute("data-cs") || "";
        if ($("recSearch")) $("recSearch").value = searchQuery;
        var id = player.id || playableRowId();
        renderTurns(id ? findRow(id) : rows[0]);
      });
    }
    if ($("recClearances")) {
      $("recClearances").addEventListener("click", function (e) {
        var item = e.target.closest("[data-t]");
        if (!item) return;
        seekTo(Number(item.getAttribute("data-t") || 0));
      });
    }
    if (copyEn) {
      copyEn.addEventListener("click", function () {
        var text = ($("recTranscript") && $("recTranscript").value) || "";
        if (!text.trim()) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            setStatus("Đã sao chép kịch bản thoại.", "ok");
          });
        }
      });
    }
    if (copyMin) {
      copyMin.addEventListener("click", function () {
        var text = ($("recMinutes") && $("recMinutes").value) || "";
        if (!text.trim()) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            setStatus("Đã sao chép biên bản bình giảng.", "ok");
          });
        }
      });
    }
    if (analyzeBtn) {
      analyzeBtn.addEventListener("click", function () {
        var id = player.id || playableRowId();
        var row = id ? findRow(id) : null;
        if (!row) {
          row = {
            id: uid(),
            name: "pasted-transcript",
            status: "ready",
            transcriptEn: ($("recTranscript") && $("recTranscript").value) || "",
            turns: []
          };
          if (!row.transcriptEn.trim()) {
            setStatus("Cần lời English (nghe file hoặc dán) rồi phân tích.", "warn");
            return;
          }
          rows.unshift(row);
        } else {
          row.transcriptEn = ($("recTranscript") && $("recTranscript").value) || row.transcriptEn || "";
        }
        setStatus("Đang đối chiếu readback REDA…", "live");
        analyzeRow(row)
          .then(function () {
            setStatus(statusAfterAnalysis(row, row.transcriptEn), "ok");
          })
          .catch(function (err) {
            setStatus((err && err.message) || "Không phân tích được.", "warn");
          });
      });
    }
    if (toHall) {
      toHall.addEventListener("click", function () {
        var text = ($("recTranscript") && $("recTranscript").value) || "";
        if (!text.trim()) {
          setStatus("Chưa có lời English. Bấm NGHE (EN) hoặc đợi ghi xong.", "warn");
          return;
        }
        try {
          localStorage.setItem("atc-pending-transcript", text);
          localStorage.setItem("atc-pending-run", "1");
        } catch (e) {}
        window.open("index.html?from=recordings", "_self");
      });
    }
    function onSeekClick(e) {
      var item = e.target.closest("[data-t]");
      if (!item) return;
      seekTo(item.getAttribute("data-t"));
    }
    if (turns) turns.addEventListener("click", onSeekClick);
    if (issues) issues.addEventListener("click", onSeekClick);
    window.addEventListener("beforeunload", function () {
      detachPlayer();
    });
  }

  bindUi();
  render();
  loadList();
})();
