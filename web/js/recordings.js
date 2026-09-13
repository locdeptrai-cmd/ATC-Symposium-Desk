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
    playing: false
  };
  var listen = {
    on: false,
    bits: []
  };
  var transcribeBusy = {};

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
    if (analysis.transcript && !row.transcriptEn) row.transcriptEn = analysis.transcript;
    if (player.id === row.id || !player.id) {
      renderTurns(row);
      renderIssues(row);
      setMinutes(row.minutesEn || "");
      if (analysis.transcript) setTranscriptBox(row.transcriptEn || analysis.transcript, "");
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
    list.innerHTML = turns
      .map(function (u) {
        var role = String(u.speaker_role || "UNKNOWN").toUpperCase();
        var roleClass = role === "ATCO" ? "is-atco" : role === "PILOT" ? "is-pilot" : "is-unknown";
        return (
          "<li data-t=\"" +
          escapeHtml(String(u.t_start || 0)) +
          "\"><span class=\"clock\">" +
          clock(u.t_start) +
          "</span><span class=\"reda-role " +
          roleClass +
          "\">" +
          escapeHtml(role) +
          "</span><span>" +
          escapeHtml(u.asr_text || u.text || "") +
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
        var title = (iss.severity || "") + " " + (iss.type || "") + (iss.field ? " · " + iss.field : "");
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

  function showRowAnalysis(row) {
    renderTurns(row);
    renderIssues(row);
    setMinutes((row && row.minutesEn) || "");
    if (row && row.transcriptEn) setTranscriptBox(row.transcriptEn, "");
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

  function refreshNow() {
    var box = $("recNow");
    var video = $("recVideo");
    var name = $("recNowName");
    var time = $("recNowTime");
    var seek = $("recSeek");
    var row = findRow(player.id);
    if (!box || !video) return;
    if (!row || !player.url) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    if (name) name.textContent = row.name;
    var cur = video.currentTime || 0;
    var dur = isFinite(video.duration) && video.duration > 0 ? video.duration : row.duration || 0;
    if (time) time.textContent = formatTime(cur) + " / " + formatTime(dur);
    if (seek && dur > 0 && !seek._dragging) {
      seek.value = String(Math.round((cur / dur) * 1000));
    }
    var showVideo = row.kind === "video" || video.videoWidth > 0;
    video.classList.toggle("is-video", showVideo);
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
      refreshNow();
    };
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

  function stopRecListen(quiet) {
    var speech = speechApi();
    if (speech && speech.listening) {
      speech.stop({ keepTape: true });
    }
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
    var wantMic = $("recMicLoop") && $("recMicLoop").checked;
    if (!wantMic) {
      setStatus("Đang ghi lời English trực tiếp từ file (không cần micro).", "live");
      return;
    }
    var speech = speechApi();
    if (!speech || !speech.available()) {
      setStatus("Đã ghi từ file. Micro không dùng được trên trình duyệt này.", "warn");
      return;
    }
    var box = $("recTranscript");
    var current = box && box.value ? box.value.trim() : "";
    listen.bits = current ? [current] : [];
    var hall = $("recHallMode") ? $("recHallMode").checked : true;
    var ok = speech.start({
      lang: "en",
      hall: hall,
      tape: true,
      commitMs: 760,
      onResult: function (res) {
        if (res.finalText) {
          listen.bits.push(res.finalText);
          if (box) box.value = listen.bits.join(" ").replace(/\s+/g, " ").trim();
        } else if (box) {
          box.value = (listen.bits.join(" ") + " " + (res.interim || "")).replace(/\s+/g, " ").trim();
        }
        if ($("recInterim")) $("recInterim").textContent = res.interim || "";
      },
      onError: function (code) {
        var map = {
          "no-engine": "Không có nhận giọng micro. Vẫn ghi lời từ file.",
          "no-permission": "Chưa cấp quyền micro. Vẫn ghi lời từ file.",
          "no-speech": "Micro không bắt được lời. Đang ghi từ file.",
          tape: "Không phát được bản ghi."
        };
        setStatus(map[code] || "Micro lỗi — đang ghi lời từ file.", "warn");
      },
      onStop: function () {
        listen.on = false;
        updateListenButtons();
        if ($("recInterim")) $("recInterim").textContent = "";
      }
    });
    if (ok) {
      setStatus("Đang ghi lời từ file, micro phụ đang nghe loa.", "live");
    }
  }

  function bindUi() {
    var drop = $("recDrop");
    var input = $("recFile");
    var btn = $("btnRecImport");
    var list = $("recList");
    var seek = $("recSeek");
    var listenBtn = $("btnRecListen");
    var listenStop = $("btnRecListenStop");
    var copyEn = $("copyRecEn");
    var copyMin = $("copyRecMinutes");
    var analyzeBtn = $("btnRecAnalyze");
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
        if (!btnEl) return;
        var item = btnEl.closest("[data-id]");
        if (!item) return;
        var id = item.getAttribute("data-id");
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
    if (seek) {
      seek.addEventListener("pointerdown", function () {
        seek._dragging = true;
      });
      seek.addEventListener("pointerup", function () {
        seek._dragging = false;
      });
      seek.addEventListener("input", function () {
        var video = $("recVideo");
        if (!video || !player.url) return;
        var dur = video.duration;
        if (!isFinite(dur) || dur <= 0) return;
        video.currentTime = (Number(seek.value) / 1000) * dur;
        refreshNow();
      });
    }
    if (listenBtn) {
      listenBtn.addEventListener("click", startRecListen);
    }
    if (listenStop) {
      listenStop.addEventListener("click", function () {
        stopRecListen();
      });
    }
    if (copyEn) {
      copyEn.addEventListener("click", function () {
        var text = ($("recTranscript") && $("recTranscript").value) || "";
        if (!text.trim()) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            setStatus("Đã sao chép lời English.", "ok");
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
