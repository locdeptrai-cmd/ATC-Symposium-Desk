(function () {
  var state = {
    role: "delegate",
    context: "conference",
    topic: "auto",
    affiliation: "sorats",
    listenLang: "en",
    hallMode: true,
    tapeMode: true,
    tapeRate: "0.85",
    enAccent: "auto",
    listening: false,
    finalBits: [],
    lastLayers: null,
    liveSeq: 0,
    suggestSeq: 0,
    units: [],
    unitCache: {},
    inflight: {},
    followTimers: []
  };

  function followLagMs() {
    if (state.tapeMode) return 560;
    return state.hallMode ? 420 : 750;
  }
  var TYPE_LAG_MS = 900;

  var $ = function (id) {
    return document.getElementById(id);
  };

  function loadState() {
    try {
      var raw = localStorage.getItem("atc-symposium-desk");
      if (!raw) return;
      var s = JSON.parse(raw);
      ["role", "context", "topic", "affiliation", "listenLang", "enAccent"].forEach(function (k) {
        if (s[k]) state[k] = s[k];
      });
      if (typeof s.hallMode === "boolean") state.hallMode = s.hallMode;
      if (typeof s.tapeMode === "boolean") state.tapeMode = s.tapeMode;
      if (s.tapeRate) state.tapeRate = String(s.tapeRate);
    } catch (e) {}
  }

  function saveState() {
    try {
      localStorage.setItem(
        "atc-symposium-desk",
        JSON.stringify({
          role: state.role,
          context: state.context,
          topic: state.topic,
          affiliation: state.affiliation,
          listenLang: state.listenLang,
          hallMode: state.hallMode,
          tapeMode: state.tapeMode,
          tapeRate: state.tapeRate,
          enAccent: state.enAccent
        })
      );
    } catch (e) {}
  }

  function setNetBadge() {
    var el = $("netBadge");
    if (!el) return;
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
      el.textContent = "ĐÃ LƯU MÁY";
      el.className = "badge badge-ok";
      return;
    }
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      el.textContent = "ĐÃ LƯU MÁY";
      el.className = "badge badge-ok";
      return;
    }
    var on = navigator.onLine;
    el.textContent = on ? "Mạng: có (dịch vẫn chạy local)" : "OFFLINE — dịch local";
    el.className = "badge " + (on ? "badge-ok" : "badge-off");
  }

  function optionHtml(list, valueKey, labelKey, current) {
    return list
      .map(function (item) {
        var sel = item.id === current ? " selected" : "";
        return "<option value=\"" + item.id + "\"" + sel + ">" + item[labelKey] + "</option>";
      })
      .join("");
  }

  function fillSelects() {
    $("role").innerHTML = optionHtml(ATC.ROLES, "id", "vi", state.role);
    $("context").innerHTML = optionHtml(ATC.CONTEXTS, "id", "vi", state.context);
    $("topic").innerHTML = optionHtml(ATC.SESSION_TOPICS, "id", "vi", state.topic);
    $("affiliation").innerHTML = optionHtml(ATC.AFFILIATIONS, "id", "vi", state.affiliation);
    $("role").value = state.role;
    $("context").value = state.context;
    $("topic").value = state.topic;
    $("affiliation").value = state.affiliation;
    updateRoleHint();
    updateListenButtons();
    updateStreamLabels();
    if ($("hallMode")) $("hallMode").checked = !!state.hallMode;
    if ($("tapeMode")) $("tapeMode").checked = !!state.tapeMode;
    if ($("tapeRate")) $("tapeRate").value = state.tapeRate || "0.85";
    if ($("enAccent")) $("enAccent").value = state.enAccent || "auto";
  }

  function updateRoleHint() {
    var role = ATC.ROLES.filter(function (r) {
      return r.id === state.role;
    })[0];
    $("roleHint").textContent = role ? role.hint + " · " + role.en : "";
  }

  function updateListenButtons() {
    $("btnEn").classList.toggle("is-active", state.listenLang === "en" && state.listening);
    $("btnVi").classList.toggle("is-active", state.listenLang === "vi" && state.listening);
    $("btnEn").setAttribute("aria-pressed", state.listenLang === "en" && state.listening ? "true" : "false");
    $("btnVi").setAttribute("aria-pressed", state.listenLang === "vi" && state.listening ? "true" : "false");
  }

  function setStatus(msg, kind) {
    var el = $("status");
    el.textContent = msg;
    el.className = "status " + (kind || "");
  }

  function translateOpts() {
    return {
      source: state.listenLang === "vi" ? "vi" : state.listenLang === "en" ? "en" : "auto",
      sessionTopic: state.topic,
      onProgress: function (p) {
        var pct = Math.round((p || 0) * 100);
        if (pct > 0 && pct < 100) {
          setStatus("Đang tải gói dịch trên máy: " + pct + "%", "live");
        }
      }
    };
  }

  function unitKey(s) {
    return String(s || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function updateStreamLabels() {
    var en = $("liveEnLabel");
    var vi = $("liveTransLabel");
    if (state.listenLang === "vi") {
      if (en) en.textContent = "Luồng 1 · Bản ghi tiếng Việt";
      if (vi) vi.textContent = "Luồng 2 · Biên dịch English (cả câu)";
    } else {
      if (en) en.textContent = "Luồng 1 · Bản ghi English";
      if (vi) vi.textContent = "Luồng 2 · Biên dịch tiếng Việt (cả câu)";
    }
  }

  function hasOnDeviceMt() {
    return typeof ATC.mtSupported === "function" && ATC.mtSupported();
  }

  function emptyLiveMessage() {
    if (!hasOnDeviceMt()) {
      return state.listenLang === "vi"
        ? "Điện thoại không có dịch cả câu (API chỉ trên Chrome/Edge máy tính). Luồng 2 sẽ thay cụm, còn sót English."
        : "Điện thoại không có dịch cả câu. Chrome/Edge máy tính mới dịch nguyên câu; trên điện thoại chỉ thay cụm ATM/ATS nên dễ còn nửa Anh nửa Việt.";
    }
    return state.listenLang === "vi"
      ? "Bấm NGHE (VI). Luồng 2 theo bản ghi, chậm hơn một nhịp rồi mới dịch cả câu sang English."
      : "Bấm NGHE DIỄN GIẢ (EN). Luồng 1 ghi English trước; luồng 2 theo sau, chậm hơn một nhịp rồi mới dịch cả câu.";
  }

  function paintUnits() {
    updateStreamLabels();
    var box = $("liveTrans");
    var meta = $("liveTransMeta");
    if (!box) return;
    var units = state.units;
    if (!units.length) {
      box.textContent = emptyLiveMessage();
      box.className = "live-trans-body is-empty";
      if (meta) meta.textContent = "";
      return;
    }
    var toVi = state.listenLang !== "vi";
    box.className = "live-trans-body";
    box.innerHTML =
      "<ul class=\"stream-units\">" +
      units
        .map(function (u) {
          if ((u.status === "waiting" || u.status === "pending") && !u.vi) {
            var wait = u.status === "waiting";
            var msg = toVi
              ? wait
                ? "Theo bản ghi English — chờ hết câu…"
                : "Đang dịch cả câu…"
              : wait
                ? "Following the transcript…"
                : "Translating the whole sentence…";
            return (
              "<li class=\"stream-unit is-pending" +
              (wait ? " is-waiting" : "") +
              "\">" +
              msg +
              "</li>"
            );
          }
          return "<li class=\"stream-unit\">" + escapeHtml(u.vi || "") + "</li>";
        })
        .join("") +
      "</ul>";
    if (meta) {
      var usedMt = false;
      var pending = false;
      var waiting = false;
      units.forEach(function (u) {
        if (u.method === "on-device-mt") usedMt = true;
        if (u.status === "pending") pending = true;
        if (u.status === "waiting") waiting = true;
      });
      meta.textContent =
        (toVi ? "EN→VI" : "VI→EN") +
        " · theo luồng 1 · chậm hơn một nhịp" +
        (usedMt
          ? " · dịch trên máy (cả câu)"
          : hasOnDeviceMt()
            ? " · cụm sẵn có"
            : " · điện thoại không có dịch cả câu — đang thay cụm, dễ sót English") +
        (waiting ? " · đang theo bản ghi…" : pending ? " · đang dịch…" : "");
    }
  }

  function joinedUnitTranslation() {
    var texts = state.units
      .map(function (u) {
        return u.vi;
      })
      .filter(Boolean);
    if (!texts.length) return null;
    var usedMt = state.units.some(function (u) {
      return u.method === "on-device-mt";
    });
    var firstEn = state.units[0] ? state.units[0].en : "";
    var sync = ATC.translate(firstEn, Object.assign(translateOpts(), { unit: "sentence" }));
    return {
      source: sync.source,
      target: sync.target,
      detected: sync.detected,
      text: texts.join(" "),
      original: transcriptValue(),
      topic: sync.topic,
      usedGist: false,
      method: usedMt ? "on-device-mt" : "sentence-units"
    };
  }

  function translateUnitAt(index) {
    var u = state.units[index];
    if (!u || !u.en) return;
    var key = unitKey(u.en);
    var cached = state.unitCache[key];
    if (cached) {
      u.vi = cached.vi;
      u.method = cached.method;
      u.status = "done";
      paintUnits();
      if (cached.method === "on-device-mt") return;
    }
    if (state.inflight[key]) return;
    var opts = Object.assign(translateOpts(), { unit: "sentence" });
    var token = ++state.liveSeq;
    u.token = token;
    if (!cached) {
      var sync = ATC.translate(u.en, opts);
      u.vi = sync.text;
      u.method = sync.method;
      u.status = "done";
      state.unitCache[key] = { vi: sync.text, method: sync.method };
      paintUnits();
    }
    if (typeof ATC.translateChunkAsync !== "function") return;
    state.inflight[key] = true;
    ATC.translateChunkAsync(u.en, opts)
      .then(function (tr) {
        delete state.inflight[key];
        if (!state.units[index] || state.units[index].token !== token) return;
        if (!tr) return;
        state.units[index].vi = tr.text;
        state.units[index].method = tr.method;
        state.units[index].status = "done";
        state.unitCache[key] = { vi: tr.text, method: tr.method };
        paintUnits();
      })
      .catch(function () {
        delete state.inflight[key];
      });
  }

  function clearFollowTimers() {
    (state.followTimers || []).forEach(function (id) {
      clearTimeout(id);
    });
    state.followTimers = [];
  }

  function scheduleFollow(index) {
    var u = state.units[index];
    if (!u) return;
    var en = u.en;
    var id = setTimeout(function () {
      var i;
      for (i = 0; i < state.units.length; i++) {
        if (state.units[i].en !== en) continue;
        if (state.units[i].status !== "waiting") continue;
        state.units[i].status = "pending";
        paintUnits();
        translateUnitAt(i);
        return;
      }
    }, followLagMs());
    state.followTimers.push(id);
  }

  function flushFollowQueue() {
    clearFollowTimers();
    state.units.forEach(function (u, i) {
      if (u.status === "waiting" || (u.status === "pending" && !u.vi)) {
        u.status = "pending";
        translateUnitAt(i);
      }
    });
  }

  function pushSpeechUnit(en) {
    var text = String(en || "").replace(/\s+/g, " ").trim();
    if (!text) return;
    state.units.push({ en: text, vi: "", status: "waiting", method: "" });
    paintUnits();
    scheduleFollow(state.units.length - 1);
  }

  function rebuildUnitsFromTranscript() {
    var text = transcriptValue();
    if (!text) {
      state.units = [];
      paintUnits();
      return;
    }
    var chunks =
      typeof ATC.splitUtterances === "function" ? ATC.splitUtterances(text) : [text];
    state.units = chunks.map(function (en) {
      var hit = state.unitCache[unitKey(en)];
      return hit
        ? { en: en, vi: hit.vi, status: "done", method: hit.method }
        : { en: en, vi: "", status: "pending", method: "" };
    });
    paintUnits();
    state.units.forEach(function (u, i) {
      if (u.method !== "on-device-mt") translateUnitAt(i);
    });
  }

  var liveTimer = null;

  function scheduleLiveTranslate() {
    if (liveTimer) clearTimeout(liveTimer);
    liveTimer = setTimeout(rebuildUnitsFromTranscript, TYPE_LAG_MS);
  }

  function warmMt(lang) {
    if (typeof ATC.ensureMt !== "function") return;
    if (lang === "vi") ATC.ensureMt("vi", "en", translateOpts().onProgress);
    else ATC.ensureMt("en", "vi", translateOpts().onProgress);
  }

  function applyLayers(layers) {
    state.lastLayers = layers;
    renderLayers(layers);
    $("results").hidden = false;
  }

  function transcriptValue() {
    return $("transcript").value.trim();
  }

  function appendFinal(text) {
    if (!text) return;
    state.finalBits.push(text);
    var all = state.finalBits.join(" ").replace(/\s+/g, " ").trim();
    $("transcript").value = all;
  }

  function errorMessage(code) {
    var map = {
      "no-engine":
        ATC.isNativeApp && ATC.isNativeApp()
          ? "Máy này chưa bật nhận dạng giọng. Dán biên bản vào ô rồi bấm DỊCH + ĐỀ XUẤT."
          : "Máy này không có Web Speech API. Dán biên bản vào ô rồi bấm DỊCH + ĐỀ XUẤT. Trên iPhone dùng Safari; Android dùng Chrome.",
      "not-allowed":
        ATC.isNativeApp && ATC.isNativeApp()
          ? "Chưa cấp quyền micro. Cài đặt máy → ATC Desk → Microphone / Speech Recognition."
          : "Chưa cấp quyền micro. iOS: Cài đặt → Safari → Microphone. Android: quyền micro cho Chrome.",
      "service-not-allowed": "Nhận dạng giọng nói bị chặn. Tải gói English/Vietnamese offline trong Cài đặt hệ thống.",
      network: "STT máy cần gói offline hoặc mạng cho nhận giọng. Dịch và câu đáp vẫn chạy khi mất mạng nếu đã có chữ.",
      "no-speech": "Không bắt được lời (tạp âm, rè, hoặc lời dính). Đưa máy gần loa/diễn giả; chế độ bản ghi vẫn ghi tiếp.",
      "audio-capture": "Micro bị chiếm hoặc tạp âm quá lớn. Gần diễn giả hơn rồi bấm nghe lại.",
      tape: "Không phát được bản ghi. Thử file mp3, wav, m4a. Bật loa — không dùng tai nghe.",
      "start-failed": "Không khởi động được micro. Thử bấm lại hoặc dán text.",
      "no-tts": "Máy không có đọc TTS. Dùng nút Sao chép và đọc trên giấy."
    };
    return map[code] || "Lỗi nhận giọng: " + code;
  }

  function listenStatus(lang) {
    if (lang !== "en") {
      return "Đang nghe tiếng Việt — luồng 1 ghi trước, luồng 2 theo bản ghi (chậm hơn một nhịp)";
    }
    if (ATC.speech.tapePlaying && ATC.speech.tapePlaying()) {
      var pct = Math.round(Number(state.tapeRate || 0.85) * 100);
      return "Đang phát bản ghi (lọc rè, " + pct + "%). Bật loa, micro hướng loa — không dùng tai nghe.";
    }
    if (state.tapeMode) {
      return "Đang nghe bản ghi / hội trường (EN) — lọc rè, tách lời dính, sửa thuật ngữ ATM";
    }
    if (state.hallMode) {
      return "Đang nghe hội trường (EN) — giọng không chuẩn / tạp âm / nói nhanh; sửa thuật ngữ ATM";
    }
    return "Đang nghe ENGLISH — luồng 1 ghi trước, luồng 2 theo bản ghi (chậm hơn một nhịp)";
  }

  function openTape(file) {
    state.tapeMode = true;
    if ($("tapeMode")) $("tapeMode").checked = true;
    saveState();
    if (state.listening) {
      ATC.speech.stop({ keepTape: true });
      state.listening = false;
    }
    var rate = Number(state.tapeRate || ($("tapeRate") && $("tapeRate").value) || 0.85);
    ATC.speech.playTape(file, {
      rate: rate,
      onEnded: function () {
        stopListen();
        setStatus("Hết bản ghi. Đã ghép lời.", "ok");
      },
      onError: function () {
        setStatus(errorMessage("tape"), "warn");
      }
    });
    startListen("en");
    if (state.listening) setStatus(listenStatus("en"), "live");
  }

  function startListen(lang) {
    if (!ATC.speech.available()) {
      setStatus(errorMessage("no-engine"), "warn");
      return;
    }
    if (state.listening && state.listenLang === lang) {
      stopListen();
      return;
    }
    state.listenLang = lang;
    if (ATC.floatingSubtitles) ATC.floatingSubtitles.reset();
    state.finalBits = transcriptValue() ? [transcriptValue()] : [];
    if (!state.units.length && transcriptValue()) rebuildUnitsFromTranscript();
    updateStreamLabels();
    warmMt(lang);
    var tape = !!state.tapeMode;
    var hall = !!state.hallMode;
    var ok = ATC.speech.start({
      lang: lang,
      hall: hall || tape,
      tape: tape,
      commitMs: tape ? 760 : hall ? 460 : 0,
      accent: state.enAccent,
      onResult: function (res) {
        var base = state.finalBits.join(" ").trim();
        if (res.finalText) {
          appendFinal(res.finalText);
          pushSpeechUnit(res.finalText);
        }
        var shown = (state.finalBits.join(" ") + " " + (res.interim || "")).replace(/\s+/g, " ").trim();
        if (!res.finalText) $("transcript").value = shown || base;
        $("interim").textContent = res.interim || "";
        if (ATC.floatingSubtitles && (res.interim || res.finalText)) {
          ATC.floatingSubtitles.push(res.interim || res.finalText, translateOpts());
        }
      },
      onError: function (code) {
        setStatus(errorMessage(code), "warn");
      },
      onStop: function () {
        state.listening = false;
        updateListenButtons();
        $("liveDot").classList.remove("is-on");
        $("interim").textContent = "";
        setStatus("Đã dừng nghe.", "");
        flushFollowQueue();
        if (transcriptValue()) runSuggest({ quiet: true });
      }
    });
    state.listening = !!ok;
    updateListenButtons();
    if (ok) {
      $("liveDot").classList.add("is-on");
      setStatus(listenStatus(lang), "live");
    }
    saveState();
  }

  function stopListen(opts) {
    opts = opts || {};
    ATC.speech.stop();
    state.listening = false;
    updateListenButtons();
    $("liveDot").classList.remove("is-on");
    $("interim").textContent = "";
    setStatus("Đã dừng nghe.", "");
    flushFollowQueue();
    if (!opts.skipSuggest && transcriptValue()) runSuggest({ quiet: true });
  }

  function runSuggest(opts) {
    opts = opts || {};
    var text = transcriptValue();
    if (text && typeof ATC.repairHeard === "function" && state.listenLang !== "vi") {
      var repaired = ATC.repairHeard(text, "en", { tape: !!state.tapeMode });
      if (repaired.text && repaired.text !== text) {
        $("transcript").value = repaired.text;
        state.finalBits = [repaired.text];
        text = repaired.text;
      }
    }
    if (!text) {
      setStatus("Chưa có nội dung. Hãy nghe hoặc dán biên bản.", "warn");
      $("transcript").focus();
      return;
    }
    if (state.listening) stopListen({ skipSuggest: true });
    warmMt(state.listenLang);
    var seq = ++state.suggestSeq;
    var tOpts = Object.assign(translateOpts(), { unit: "sentence" });
    rebuildUnitsFromTranscript();
    var sync = joinedUnitTranslation() || ATC.translate(text, tOpts);
    applyLayers(
      ATC.buildLayers({
        text: text,
        listenLang: tOpts.source,
        role: state.role,
        context: state.context,
        sessionTopic: state.topic,
        affiliation: state.affiliation,
        chairTitle: "Chair",
        translation: sync
      })
    );
    paintUnits();
    if (!opts.quiet) $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    setStatus("Đã dịch từng câu/cụm song song với bản ghi.", "ok");
    var chunks =
      typeof ATC.splitUtterances === "function" ? ATC.splitUtterances(text) : [text];
    if (typeof ATC.translateManyAsync !== "function") return;
    ATC.translateManyAsync(chunks, tOpts).then(function (tr) {
      if (seq !== state.suggestSeq) return;
      if (!tr) return;
      applyLayers(
        ATC.buildLayers({
          text: text,
          listenLang: tOpts.source,
          role: state.role,
          context: state.context,
          sessionTopic: state.topic,
          affiliation: state.affiliation,
          chairTitle: "Chair",
          translation: tr
        })
      );
      paintUnits();
      if (tr.method === "on-device-mt") setStatus("Đã dịch trên máy từng câu.", "ok");
    });
  }

  function renderLayers(L) {
    $("topicChip").textContent = L.topic.label.vi + " · " + L.intent.replace(/_/g, " ");
    $("caution").hidden = !L.caution;
    $("caution").textContent = L.caution || "";

    $("t1h").textContent = L.translation.heading;
    $("t1").textContent = L.translation.text;
    $("t1").className = /en\s*→\s*vi/i.test(L.translation.direction) ? "vi-primary" : "en-block";
    $("t1meta").textContent = L.translation.method + " · " + L.translation.direction;

    $("t2en").textContent = L.statement.en;
    $("t2vi").textContent = L.statement.vi;

    $("t3en").textContent = L.short.en;
    $("t3vi").textContent = L.short.vi;
    $("t3meta").textContent = L.short.words + " words · ~" + L.short.seconds + " s (mục tiêu 60–90 s)";

    $("t4points").innerHTML = L.points
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

    $("t4gloss").innerHTML = L.glossary
      .map(function (g) {
        return (
          "<tr><th>" +
          escapeHtml(g.abbr) +
          "</th><td>" +
          escapeHtml(g.en) +
          "</td><td>" +
          escapeHtml(g.vi) +
          "</td></tr>"
        );
      })
      .join("");

    $("t4docs").innerHTML = (L.docs || [])
      .map(function (d) {
        return "<li>" + escapeHtml(d) + "</li>";
      })
      .join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function copyText(text, btn) {
    function ok() {
      if (!btn) return;
      var old = btn.textContent;
      btn.textContent = "Đã chép";
      setTimeout(function () {
        btn.textContent = old;
      }, 1200);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok).catch(function () {
        fallbackCopy(text);
        ok();
      });
    } else {
      fallbackCopy(text);
      ok();
    }
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch (e) {}
    document.body.removeChild(ta);
  }

  function speakLayer(which) {
    if (!state.lastLayers) return;
    ATC.speech.silence();
    var text =
      which === "short" ? state.lastLayers.short.en : state.lastLayers.statement.en;
    setStatus("Đang đọc English — nghe trước khi giơ mic.", "ok");
    ATC.speech.speak(text, {
      lang: "en-GB",
      rate: 0.92,
      onend: function () {
        setStatus("Hết bản đọc.", "");
      },
      onError: function (c) {
        setStatus(errorMessage(c), "warn");
      }
    });
  }

  function renderSamples() {
    var box = $("samples");
    box.innerHTML = ATC.SAMPLES.map(function (s) {
      return (
        "<button type=\"button\" class=\"chip\" data-sample=\"" +
        s.id +
        "\">" +
        escapeHtml(s.label) +
        "</button>"
      );
    }).join("");
    box.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-sample]");
      if (!btn) return;
      var s = ATC.SAMPLES.filter(function (x) {
        return x.id === btn.getAttribute("data-sample");
      })[0];
      if (!s) return;
      state.listenLang = s.lang;
      if (s.topic) {
        state.topic = "auto";
        $("topic").value = "auto";
      }
      $("transcript").value = s.text;
      state.finalBits = [s.text];
      updateListenButtons();
      runSuggest();
    });
  }

  function bind() {
    $("role").addEventListener("change", function () {
      state.role = this.value;
      updateRoleHint();
      saveState();
      if (transcriptValue()) runSuggest();
    });
    $("context").addEventListener("change", function () {
      state.context = this.value;
      saveState();
      if (transcriptValue()) runSuggest();
    });
    $("topic").addEventListener("change", function () {
      state.topic = this.value;
      saveState();
    });
    $("affiliation").addEventListener("change", function () {
      state.affiliation = this.value;
      saveState();
      if (transcriptValue()) runSuggest();
    });
    $("btnEn").addEventListener("click", function () {
      startListen("en");
    });
    $("btnVi").addEventListener("click", function () {
      startListen("vi");
    });
    if ($("hallMode")) {
      $("hallMode").addEventListener("change", function () {
        state.hallMode = !!this.checked;
        saveState();
      });
    }
    if ($("tapeMode")) {
      $("tapeMode").addEventListener("change", function () {
        state.tapeMode = !!this.checked;
        saveState();
      });
    }
    if ($("tapeRate")) {
      $("tapeRate").addEventListener("change", function () {
        state.tapeRate = this.value || "0.85";
        saveState();
      });
    }
    if ($("enAccent")) {
      $("enAccent").addEventListener("change", function () {
        state.enAccent = this.value || "auto";
        saveState();
      });
    }
    if ($("btnTape") && $("tapeFile")) {
      $("btnTape").addEventListener("click", function () {
        $("tapeFile").click();
      });
      $("tapeFile").addEventListener("change", function () {
        var file = this.files && this.files[0];
        this.value = "";
        if (file) openTape(file);
      });
    }
    $("btnStop").addEventListener("click", stopListen);
    $("btnGo").addEventListener("click", function () {
      runSuggest();
    });
    $("transcript").addEventListener("input", function () {
      state.finalBits = transcriptValue() ? [transcriptValue()] : [];
      scheduleLiveTranslate();
    });
    $("copyLive").addEventListener("click", function () {
      var t = state.units
        .map(function (u) {
          return u.vi;
        })
        .filter(Boolean)
        .join(" ");
      if (t) copyText(t, this);
    });
    var copyEn = $("copyEn");
    if (copyEn) {
      copyEn.addEventListener("click", function () {
        var t = transcriptValue();
        if (t) copyText(t, this);
      });
    }
    $("btnClear").addEventListener("click", function () {
      stopListen({ skipSuggest: true });
      ATC.speech.silence();
      state.finalBits = [];
      if (ATC.floatingSubtitles) ATC.floatingSubtitles.reset();
      state.units = [];
      state.unitCache = {};
      state.inflight = {};
      clearFollowTimers();
      state.lastLayers = null;
      $("transcript").value = "";
      $("interim").textContent = "";
      $("results").hidden = true;
      paintUnits();
      setStatus("Đã xóa.", "");
    });
    $("copyT1").addEventListener("click", function () {
      if (state.lastLayers) copyText(state.lastLayers.translation.text, this);
    });
    $("copyT2").addEventListener("click", function () {
      if (state.lastLayers) copyText(state.lastLayers.statement.en, this);
    });
    $("copyT3").addEventListener("click", function () {
      if (state.lastLayers) copyText(state.lastLayers.short.en, this);
    });
    $("speakT2").addEventListener("click", function () {
      speakLayer("full");
    });
    $("speakT3").addEventListener("click", function () {
      speakLayer("short");
    });
    $("btnSpeakFull").addEventListener("click", function () {
      speakLayer("full");
    });
    $("btnSpeakShort").addEventListener("click", function () {
      speakLayer("short");
    });
    window.addEventListener("online", setNetBadge);
    window.addEventListener("offline", setNetBadge);
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) ATC.speech.silence();
    });
  }

  function setupNativeMtPack() {
    var box = $("mtPack");
    var btn = $("btnMtPack");
    if (!box || !btn) return;
    if (typeof ATC.isNativeApp !== "function" || !ATC.isNativeApp()) return;
    box.hidden = false;
    if (typeof ATC.nativeMtStatus === "function") {
      ATC.nativeMtStatus().then(function (st) {
        if (st && st.ready) box.hidden = true;
      });
    }
    btn.addEventListener("click", function () {
      setStatus("Đang tải gói dịch EN+VI trên máy…", "live");
      ATC.prepareNativeMt(function (p) {
        var pct = Math.round((p || 0) * 100);
        setStatus("Đang tải gói dịch: " + pct + "%", "live");
      })
        .then(function () {
          box.hidden = true;
          setStatus("Đã có gói dịch cả câu. Tắt mạng vẫn dịch được.", "ok");
        })
        .catch(function () {
          setStatus("Không tải được gói dịch. Cần Wi-Fi một lần (không cần laptop).", "warn");
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadState();
    fillSelects();
    renderSamples();
    bind();
    setNetBadge();
    paintUnits();
    setupNativeMtPack();
    if (!ATC.speech.available()) {
      setStatus(errorMessage("no-engine"), "warn");
    } else {
      setStatus("Sẵn sàng. Nghe diễn giả hoặc dán biên bản.", "");
    }
    try {
      var pending = localStorage.getItem("atc-pending-transcript");
      var run = localStorage.getItem("atc-pending-run");
      if (pending && run) {
        localStorage.removeItem("atc-pending-run");
        $("transcript").value = pending;
        state.finalBits = [pending];
        state.listenLang = "en";
        saveState();
        setStatus("Đã chép lời English từ bản ghi. Đang dịch + đề xuất…", "live");
        runSuggest();
      }
    } catch (e) {}
  });
})();
