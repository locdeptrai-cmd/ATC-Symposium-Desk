(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  var VI_CHAR = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
  var VI_CHAR_ALL = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/gi;

  function escapeRe(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function normalizeSpace(s) {
    return String(s || "")
      .replace(/\s+/g, " ")
      .replace(/\s+([,.;:!?])/g, "$1")
      .replace(/([(\[])\s+/g, "$1")
      .replace(/\s+([)\]])/g, "$1")
      .trim();
  }

  function capitalizeSentence(s) {
    if (!s) return s;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function countWords(s) {
    return String(s || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean).length;
  }

  ATC.countWords = countWords;
  ATC.estimateSeconds = function (enText) {
    return Math.max(8, Math.round((countWords(enText) / 125) * 60));
  };

  ATC.detectLang = function (text) {
    var t = String(text || "").trim();
    if (!t) return "unknown";
    var viHits = (t.match(VI_CHAR_ALL) || []).length;
    var viWords = (
      t.match(
        /\b(và|của|các|là|không|đã|chưa|hay|cho|với|trong|đơn vị|xin|hỏi|chúng tôi|kính|thưa)\b/gi
      ) || []
    ).length;
    if (viHits >= 2 || viWords >= 2) return "vi";
    if (/[A-Za-z]{3,}/.test(t)) return "en";
    return viHits ? "vi" : "en";
  };

  ATC.detectTopic = function (text, preferred) {
    if (preferred && preferred !== "auto" && ATC.TOPIC_PACKS[preferred]) {
      var forced = scoreTopic(text, ATC.TOPIC_PACKS[preferred]);
      var bestAuto = bestTopic(text);
      if (bestAuto && bestAuto.score >= forced + 3 && bestAuto.id !== preferred) {
        return { id: bestAuto.id, score: bestAuto.score, session: preferred, mismatch: true };
      }
      return { id: preferred, score: Math.max(forced, 1), session: preferred, mismatch: false };
    }
    var best = bestTopic(text);
    return best || { id: "general", score: 0, session: preferred || "auto", mismatch: false };
  };

  function scoreTopic(text, pack) {
    var hay = String(text || "").toLowerCase();
    var n = 0;
    (pack.keywords || []).forEach(function (k) {
      if (hay.indexOf(String(k).toLowerCase()) !== -1) n += 1;
    });
    return n;
  }

  function bestTopic(text) {
    var best = null;
    Object.keys(ATC.TOPIC_PACKS).forEach(function (id) {
      if (id === "general") return;
      var s = scoreTopic(text, ATC.TOPIC_PACKS[id]);
      if (!best || s > best.score) best = { id: id, score: s };
    });
    if (!best || best.score < 1) return { id: "general", score: 0 };
    return best;
  }

  ATC.detectIntent = function (text) {
    var t = String(text || "").toLowerCase();
    if (/four minutes|hết giờ|time is short|coffee break|remaining questions|close this item/.test(t)) {
      return "time_pressure";
    }
    if (/phản biện|không đồng ý|we cannot accept|we disagree|rebut/.test(t)) return "rebuttal";
    if (/đề nghị|we propose|we recommend|we suggest/.test(t)) return "proposal";
    if (/làm rõ|clarify|what do you mean/.test(t)) return "clarification";
    if (
      /xin hỏi|cho hỏi|could (the|you)|can (the|you)|whether|has the|have you|\?/.test(t)
    ) {
      if (/hay (mới )?chỉ|or (whether )?(only|just)|chưa, hay/.test(t)) return "question_alternative";
      return "question";
    }
    return "statement";
  };

  function applyRegexPhrases(text, direction) {
    var out = text;
    (ATC.REGEX_PHRASES || []).forEach(function (p) {
      if (direction === "vi-en" && p.vi && p.en) out = out.replace(p.vi, p.en);
      if (direction === "en-vi" && p.vi && p.viOut) out = out.replace(p.vi, p.viOut);
    });
    return out;
  }

  function applyLiterals(text, fromKey, toKey) {
    var items = [];
    (ATC.PHRASES || []).forEach(function (p) {
      if (p[fromKey] && p[toKey]) items.push({ from: p[fromKey], to: p[toKey] });
    });
    (ATC.TERMS || []).forEach(function (p) {
      if (p.abbr) {
        items.push({ from: p.abbr, to: p.abbr, keep: true });
      }
      if (p[fromKey] && (p[toKey] || p.abbr)) {
        items.push({ from: p[fromKey], to: p[toKey] || p.abbr });
      }
    });
    items.sort(function (a, b) {
      return String(b.from).length - String(a.from).length;
    });
    var out = text;
    items.forEach(function (it) {
      if (!it.from || it.keep) return;
      if (String(it.from).length < 3) return;
      var from = String(it.from);
      var re = /^[A-Za-z]/.test(from)
        ? new RegExp("\\b" + escapeRe(from) + "\\b", "gi")
        : new RegExp(escapeRe(from), "gi");
      out = out.replace(re, it.to);
    });
    return out;
  }

  var lexiconCompiled = null;

  function compileLexicon() {
    if (lexiconCompiled) return lexiconCompiled;
    var rows = (ATC.EN_VI_LEXICON || []).slice().sort(function (a, b) {
      return String(b[0]).length - String(a[0]).length;
    });
    lexiconCompiled = rows
      .filter(function (row) {
        return row && row[0];
      })
      .map(function (row) {
        var from = String(row[0]);
        return {
          from: from,
          words: from.trim().split(/\s+/).length,
          re: new RegExp("\\b" + escapeRe(from) + "\\b", "gi"),
          to: row[1] == null ? "" : String(row[1])
        };
      });
    return lexiconCompiled;
  }

  function applyLexiconEnVi(text, skipUnigrams) {
    var out = String(text || "");
    var compiled = compileLexicon();
    compiled.forEach(function (it) {
      if (it.words < 2) return;
      out = out.replace(it.re, it.to);
    });
    if (skipUnigrams) return normalizeSpace(out);
    var tokenMap = {};
    compiled.forEach(function (it) {
      if (it.words === 1) tokenMap[it.from.toLowerCase()] = it.to;
    });
    out = out.split(/(\s+)/).map(function (tok) {
      if (!tok || /^\s+$/.test(tok)) return tok;
      if (/[^\x00-\x7F]/.test(tok)) return tok;
      var m = tok.match(/^([^A-Za-z]*)([A-Za-z][A-Za-z'-]*)([^A-Za-z]*)$/);
      if (!m) return tok;
      var core = m[2];
      if (core === core.toUpperCase() && core.length > 1) return tok;
      var hit = tokenMap[core.toLowerCase()];
      if (hit == null) return tok;
      return m[1] + hit + m[3];
    }).join("");
    return normalizeSpace(out);
  }

  ATC.splitUtterances = function (text) {
    var t = normalizeSpace(text);
    if (!t) return [];
    var parts = [];
    var re = /[^.?!;]+(?:[.?!;]+|$)/g;
    var m;
    while ((m = re.exec(t))) {
      var chunk = normalizeSpace(m[0]);
      if (chunk) parts.push(chunk);
    }
    if (!parts.length) parts = [t];
    if (parts.length === 1 && countWords(parts[0]) > 28) {
      var clauses = parts[0].split(/,\s+/);
      if (clauses.length > 1) {
        var packed = [];
        var buf = "";
        clauses.forEach(function (clause, i) {
          buf = buf ? buf + ", " + clause : clause;
          if (countWords(buf) >= 16 || i === clauses.length - 1) {
            packed.push(normalizeSpace(buf));
            buf = "";
          }
        });
        parts = packed.filter(Boolean);
      } else {
        var words = parts[0].split(/\s+/);
        parts = [];
        var i;
        for (i = 0; i < words.length; i += 22) {
          parts.push(words.slice(i, i + 22).join(" "));
        }
      }
    }
    return parts;
  };

  var dictMulti = null;
  var dictReady = false;

  function ensureDictIndex() {
    if (dictReady) return;
    dictReady = true;
    dictMulti = [];
    var map = ATC.EN_VI_DICT || {};
    Object.keys(map).forEach(function (k) {
      if (k.indexOf(" ") >= 0) dictMulti.push(k);
    });
    dictMulti.sort(function (a, b) {
      return b.length - a.length;
    });
  }

  function dictLookup(word) {
    var map = ATC.EN_VI_DICT || {};
    var w = String(word || "").toLowerCase();
    if (!w) return null;
    if (map[w]) return map[w];
    var stems = [];
    if (w.length > 5 && /ies$/.test(w)) stems.push(w.slice(0, -3) + "y");
    if (w.length > 5 && /ing$/.test(w)) {
      stems.push(w.slice(0, -3));
      stems.push(w.slice(0, -3) + "e");
      if (w.length > 6 && w.charAt(w.length - 4) === w.charAt(w.length - 5)) {
        stems.push(w.slice(0, -4));
      }
    }
    if (w.length > 4 && /ed$/.test(w)) {
      stems.push(w.slice(0, -2));
      stems.push(w.slice(0, -1));
    }
    if (w.length > 4 && /es$/.test(w)) stems.push(w.slice(0, -2));
    if (w.length > 3 && /s$/.test(w) && !/ss$/.test(w)) stems.push(w.slice(0, -1));
    var i;
    for (i = 0; i < stems.length; i++) {
      if (map[stems[i]]) return map[stems[i]];
    }
    return null;
  }

  function applyDictEnVi(text) {
    ensureDictIndex();
    var map = ATC.EN_VI_DICT;
    if (!map) return text;
    var out = String(text || "");
    dictMulti.forEach(function (key) {
      var re = new RegExp("\\b" + escapeRe(key) + "\\b", "gi");
      out = out.replace(re, function (m) {
        if (/[^\x00-\x7F]/.test(m)) return m;
        return map[key];
      });
    });
    return out
      .split(/(\s+)/)
      .map(function (tok, i, parts) {
        if (!tok || /^\s+$/.test(tok)) return tok;
        if (/[^\x00-\x7F]/.test(tok)) return tok;
        var m = tok.match(/^([^A-Za-z]*)([A-Za-z][A-Za-z'-]*)([^A-Za-z]*)$/);
        if (!m) return tok;
        var core = m[2];
        if (core === core.toUpperCase() && core.length > 1) return tok;
        if (core.length < 3) return tok;
        var nearVi =
          VI_CHAR.test(parts[i - 2] || "") || VI_CHAR.test(parts[i + 2] || "");
        if (nearVi && core.length <= 3) return tok;
        if (/^(tin|hay|lead|can|may|pan|pen|pin|son|sun|arm|lie|box)$/i.test(core)) {
          return tok;
        }
        var hit = dictLookup(core);
        if (hit == null) return tok;
        return m[1] + hit + m[3];
      })
      .join("");
  }

  function canonicalizeAbbr(text) {
    var out = String(text || "");
    (ATC.TERMS || []).forEach(function (p) {
      if (!p.abbr || String(p.abbr).length < 2) return;
      var re = new RegExp("\\b" + escapeRe(p.abbr) + "\\b", "gi");
      out = out.replace(re, p.abbr);
    });
    return out;
  }

  function leftoverViRatio(text) {
    var t = String(text || "");
    if (!t) return 0;
    var vi = (t.match(VI_CHAR_ALL) || []).length;
    return vi / Math.max(t.length, 1);
  }

  function leftoverEnTokenRatio(text) {
    var t = String(text || "");
    var words = t.split(/\s+/).filter(Boolean);
    if (!words.length) return 0;
    var en = 0;
    words.forEach(function (w) {
      if (/^[A-Za-z][A-Za-z'-]*$/.test(w) && w !== w.toUpperCase()) en += 1;
    });
    return en / words.length;
  }

  var VI_PARTICLE =
    /\b(xin hỏi|cho hỏi|kính thưa|đơn vị|chúng tôi|đã|chưa|hay|thì|mà|được|những|các|của|là|này|đó|nên|với|trong|một|cũng|rất|để|không|phải|chỉ|mới|vào|câu hỏi|ạ)\b/gi;

  function stripResidualVi(s) {
    s = s.replace(VI_PARTICLE, " ");
    s = s.replace(VI_CHAR_ALL, "");
    return s;
  }

  function cleanupEn(s) {
    s = stripResidualVi(s);
    s = normalizeSpace(s);
    s = s.replace(/\b(the the|a a|an an)\b/gi, function (m) {
      return m.split(" ")[0];
    });
    s = s.replace(/\bwhether whether\b/gi, "whether");
    s = s.replace(/\bor or\b/gi, "or");
    s = s.replace(/\b(could the unit confirm)\s+(whether)?/i, "Could the unit confirm whether");
    s = s.replace(/^whether /i, "Whether ");
    s = s.replace(/\s+,/g, ",");
    s = s.replace(/[?]{2,}/g, "?");
    s = s.replace(/\s+\?/g, "?");
    if (!/[.!?]$/.test(s)) s += /whether|could|has |have |what |how |why /i.test(s) ? "?" : ".";
    return capitalizeSentence(s);
  }

  function dropStrayEnglishArticles(s) {
    var parts = String(s || "").split(/(\s+)/);
    return parts
      .map(function (tok, i) {
        if (!/^(a|an|the)$/i.test(tok)) return tok;
        var next = parts[i + 2] || "";
        if (VI_CHAR.test(next)) return tok;
        return "";
      })
      .join("");
  }

  function cleanupVi(s) {
    s = normalizeSpace(s);
    s = s.replace(/\s+\?/g, "?");
    if (!/[.!?]$/.test(s)) s += s.indexOf("?") >= 0 ? "" : ".";
    return capitalizeSentence(s);
  }

  ATC.translate = function (raw, opts) {
    opts = opts || {};
    var text = normalizeSpace(raw);
    text = text.replace(/[\u2018\u2019\u02BC]/g, "'");
    var detected = ATC.detectLang(text);
    var source = opts.source && opts.source !== "auto" ? opts.source : detected;
    if (source === "unknown") source = "en";
    var target = source === "vi" ? "en" : "vi";
    if (opts.target) target = opts.target;
    var saved = ATC.library && ATC.library.exact(text, source);
    if (saved && target !== source) {
      return { source: source, target: target, detected: detected, text: saved[target], original: text,
        topic: ATC.detectTopic(text, opts.sessionTopic), usedGist: false, method: "offline-library", entryId: saved.id };
    }

    var direction = source === "vi" ? "vi-en" : "en-vi";
    var sentenceUnit = opts.unit === "sentence";
    var working = canonicalizeAbbr(text);
    working = applyRegexPhrases(working, direction);
    working = applyLiterals(working, source, target);
    if (direction === "en-vi") {
      working = applyLexiconEnVi(working, sentenceUnit);
      if (!sentenceUnit) {
        working = applyDictEnVi(working);
        working = dropStrayEnglishArticles(working);
      }
      working = working.replace(/'s\b/g, "");
    }
    var viLeft = leftoverViRatio(working);
    var changed =
      normalizeSpace(working).toLowerCase() !== normalizeSpace(text).toLowerCase();
    working = direction === "vi-en" ? cleanupEn(working) : cleanupVi(working);

    var topicInfo = ATC.detectTopic(text, opts.sessionTopic);
    var pack = ATC.TOPIC_PACKS[topicInfo.id] || ATC.TOPIC_PACKS.general;

    var usedGist = false;
    if (!sentenceUnit && direction === "vi-en" && viLeft > 0.12 && !changed) {
      usedGist = true;
      working =
        "The speaker asked, in substance, " +
        pack.gistEn +
        (/\?/.test(text) ? "." : ".");
      working = cleanupEn(working);
    } else if (!sentenceUnit && direction === "en-vi" && leftoverViRatio(working) < 0.02) {
      usedGist = true;
      working = cleanupVi(working + " — Diễn giả đang nói về: " + pack.gistVi);
    }

    return {
      source: source,
      target: target,
      detected: detected,
      text: working,
      original: text,
      topic: topicInfo,
      usedGist: usedGist,
      method: usedGist
        ? "lexicon+topic-hint"
        : sentenceUnit
          ? "sentence-phrases"
          : "phrase+glossary"
    };
  };

  var mtSlots = {};

  function translatorCtor() {
    return typeof root.Translator === "function" ? root.Translator : null;
  }

  ATC.mtSupported = function () {
    return ATC.nativeMtAvailable() || !!translatorCtor();
  };

  ATC.ensureMt = function (source, target, onProgress) {
    source = String(source || "en");
    target = String(target || "vi");
    var key = source + "-" + target;

    if (typeof ATC.nativeMtAvailable === "function" && ATC.nativeMtAvailable()) {
      if (mtSlots[key] && mtSlots[key].translator) {
        return Promise.resolve(mtSlots[key]);
      }
      if (mtSlots[key] && mtSlots[key].promise) {
        return mtSlots[key].promise;
      }
      var nativeSlot = { translator: null, status: "starting", progress: 0, method: "mlkit" };
      nativeSlot.promise = ATC.prepareNativeMt(onProgress)
        .then(function (ok) {
          if (!ok) return null;
          nativeSlot.translator = {
            translate: function (text) {
              return ATC.nativeTranslate(text, source, target);
            }
          };
          nativeSlot.status = "ready";
          nativeSlot.progress = 1;
          return nativeSlot;
        })
        .catch(function () {
          nativeSlot.status = "error";
          delete mtSlots[key];
          return null;
        });
      mtSlots[key] = nativeSlot;
      return nativeSlot.promise;
    }

    var Ctor = translatorCtor();
    if (!Ctor) {
      return Promise.resolve(null);
    }
    if (mtSlots[key] && mtSlots[key].translator) {
      return Promise.resolve(mtSlots[key]);
    }
    if (mtSlots[key] && mtSlots[key].promise) {
      return mtSlots[key].promise;
    }
    var slot = { translator: null, status: "starting", progress: 0 };
    slot.promise = Promise.resolve()
      .then(function () {
        if (typeof Ctor.availability === "function") {
          return Ctor.availability({
            sourceLanguage: source,
            targetLanguage: target
          });
        }
        return "available";
      })
      .then(function (avail) {
        if (avail === "unavailable") {
          slot.status = "unavailable";
          return null;
        }
        slot.status = avail === "available" ? "ready" : "downloading";
        var opts = {
          sourceLanguage: source,
          targetLanguage: target
        };
        if (avail !== "available") {
          opts.monitor = function (m) {
            m.addEventListener("downloadprogress", function (ev) {
              slot.progress = ev && typeof ev.loaded === "number" ? ev.loaded : 0;
              if (onProgress) onProgress(slot.progress);
            });
          };
        }
        return Ctor.create(opts);
      })
      .then(function (tr) {
        if (!tr) return null;
        slot.translator = tr;
        slot.status = "ready";
        slot.progress = 1;
        return slot;
      })
      .catch(function () {
        slot.status = "error";
        delete mtSlots[key];
        return null;
      });
    mtSlots[key] = slot;
    return slot.promise;
  };

  ATC.translateAsync = function (raw, opts) {
    opts = opts || {};
    var sync = ATC.translate(raw, opts);
    var source = sync.source === "vi" ? "vi" : "en";
    var target = source === "vi" ? "en" : "vi";
    if (opts.skipMt || sync.method === "offline-library") return Promise.resolve(sync);
    return ATC.ensureMt(source, target, opts.onProgress).then(function (slot) {
      if (!slot || !slot.translator || typeof slot.translator.translate !== "function") {
        return sync;
      }
      var prepared = canonicalizeAbbr(sync.original);
      return Promise.resolve(slot.translator.translate(prepared)).then(function (mtText) {
        var working = String(mtText || "").trim();
        if (!working) return sync;
        working = target === "vi" ? cleanupVi(working) : cleanupEn(working);
        if (target === "vi" && leftoverEnTokenRatio(working) > 0.85) return sync;
        return {
          source: source,
          target: target,
          detected: sync.detected,
          text: working,
          original: sync.original,
          topic: sync.topic,
          usedGist: false,
          method: "on-device-mt"
        };
      });
    }).catch(function () {
      return sync;
    });
  };

  ATC.translateChunkAsync = function (raw, opts) {
    opts = opts || {};
    var next = {};
    Object.keys(opts).forEach(function (k) {
      next[k] = opts[k];
    });
    next.unit = "sentence";
    return ATC.translateAsync(raw, next);
  };

  ATC.translateManyAsync = function (chunks, opts) {
    var list = (chunks || []).map(function (c) {
      return String(c || "").trim();
    }).filter(Boolean);
    if (!list.length) {
      return Promise.resolve(ATC.translate("", opts));
    }
    return Promise.all(
      list.map(function (c) {
        return ATC.translateChunkAsync(c, opts);
      })
    ).then(function (trs) {
      var usedMt = false;
      var i;
      for (i = 0; i < trs.length; i++) {
        if (trs[i].method === "on-device-mt") usedMt = true;
      }
      return {
        source: trs[0].source,
        target: trs[0].target,
        detected: trs[0].detected,
        text: trs
          .map(function (t) {
            return t.text;
          })
          .join(" "),
        original: list.join(" "),
        topic: trs[0].topic,
        usedGist: false,
        method: usedMt ? "on-device-mt" : "sentence-units"
      };
    });
  };

  ATC.glossaryForTopic = function (topicId, text) {
    var pack = ATC.TOPIC_PACKS[topicId] || ATC.TOPIC_PACKS.general;
    var wanted = {};
    (pack.glossary || []).forEach(function (a) {
      wanted[a] = true;
    });
    var hay = String(text || "").toUpperCase();
    var out = [];
    (ATC.TERMS || []).forEach(function (term) {
      if (!term.abbr) return;
      if (wanted[term.abbr] || hay.indexOf(term.abbr.toUpperCase()) !== -1) {
        out.push({
          abbr: term.abbr,
          en: term.en,
          vi: term.vi
        });
      }
    });
    var seen = {};
    return out.filter(function (row) {
      if (seen[row.abbr]) return false;
      seen[row.abbr] = true;
      return true;
    });
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
