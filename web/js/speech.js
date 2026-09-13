(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  function Recognition() {
    var Ctor = root.SpeechRecognition || root.webkitSpeechRecognition;
    return Ctor ? new Ctor() : null;
  }

  function nativeSpeech() {
    if (typeof ATC.isNativeApp !== "function" || !ATC.isNativeApp()) return null;
    var C = root.Capacitor;
    var plugins = (C && C.Plugins) || {};
    return plugins.SpeechRecognition || null;
  }

  function mapNativeError(err) {
    var msg = String((err && (err.message || err.error || err)) || "");
    if (/permission|not allowed|MISSING|denied/i.test(msg)) return "not-allowed";
    if (/network/i.test(msg)) return "network";
    if (/no.?match|no.?speech|ERROR_NO_MATCH|ERROR_SPEECH_TIMEOUT/i.test(msg)) {
      return "no-speech";
    }
    if (/not available|unavailable/i.test(msg)) return "no-engine";
    return "start-failed";
  }

  function localeFor(opts) {
    if (opts.lang === "vi") return "vi-VN";
    var accent = opts.accent || "auto";
    if (accent === "gb") return "en-GB";
    if (accent === "in") return "en-IN";
    if (accent === "au") return "en-AU";
    if (accent === "us") return "en-US";
    return "en-US";
  }

  function attachGrammar(rec) {
    var Ctor = root.SpeechGrammarList || root.webkitSpeechGrammarList;
    if (!Ctor || typeof ATC.grammarFromTerms !== "function") return;
    try {
      var list = new Ctor();
      list.addFromString(ATC.grammarFromTerms(), 1);
      rec.grammars = list;
    } catch (e) {}
  }

  function pickResult(results, i, lang) {
    var row = results[i];
    if (!row || !row.length) return { transcript: "", confidence: 0 };
    if (lang === "vi") {
      return { transcript: row[0].transcript, confidence: row[0].confidence };
    }
    var alts = [];
    var n;
    for (n = 0; n < row.length; n++) {
      alts.push({ transcript: row[n].transcript, confidence: row[n].confidence });
    }
    if (typeof ATC.pickHeardAlternative === "function") {
      var picked = ATC.pickHeardAlternative(alts);
      if (picked) return { transcript: picked.text, confidence: picked.confidence, fixes: picked.fixes };
    }
    return { transcript: row[0].transcript, confidence: row[0].confidence };
  }

  function repairChunk(text, lang, tape) {
    if (lang === "vi" || typeof ATC.repairHeard !== "function") return spaceTrim(text);
    return ATC.repairHeard(text, "en", { tape: !!tape }).text;
  }

  function spaceTrim(s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  function looksNoisy(conf, hall, tape) {
    if (!isFinite(conf) || conf <= 0) return false;
    if (tape) return conf < 0.08;
    return hall ? conf < 0.12 : conf < 0.22;
  }

  ATC.speech = {
    rec: null,
    listening: false,
    desiredLang: "en-US",
    _nativeInterim: "",
    _nativeRestartTimer: 0,
    _commitTimer: 0,
    _stableInterim: "",
    _lastFinal: "",
    _tape: null,

    available: function () {
      if (nativeSpeech()) return true;
      return !!(root.SpeechRecognition || root.webkitSpeechRecognition);
    },

    ttsAvailable: function () {
      return !!(root.speechSynthesis && root.SpeechSynthesisUtterance);
    },

    start: function (opts) {
      opts = opts || {};
      if (this.listening) this.stop({ keepTape: true });
      if (nativeSpeech()) return this._startNative(opts);
      return this._startWeb(opts);
    },

    _startWeb: function (opts) {
      var self = this;
      var rec = Recognition();
      if (!rec) {
        if (opts.onError) opts.onError("no-engine");
        return false;
      }
      var tape = !!opts.tape;
      var hall = opts.hall !== false || tape;
      var lang = opts.lang === "vi" ? "vi" : "en";
      this.desiredLang = localeFor(opts);
      rec.lang = this.desiredLang;
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = hall || tape ? 5 : 3;
      attachGrammar(rec);
      this._stableInterim = "";
      this._lastFinal = "";
      if (this._commitTimer) {
        root.clearTimeout(this._commitTimer);
        this._commitTimer = 0;
      }

      function emitFinal(text) {
        var cleaned = repairChunk(text, lang, tape);
        if (!cleaned) return;
        if (typeof ATC.mergeHeardOverlap === "function") {
          var merged = ATC.mergeHeardOverlap(self._lastFinal, cleaned);
          if (foldEq(merged, self._lastFinal)) return;
          if (foldEq(cleaned, self._lastFinal)) return;
        }
        self._lastFinal = cleaned;
        self._stableInterim = "";
        if (opts.onResult) opts.onResult({ finalText: cleaned, interim: "" });
      }

      function foldEq(a, b) {
        return String(a || "").toLowerCase().replace(/\s+/g, " ").trim() ===
          String(b || "").toLowerCase().replace(/\s+/g, " ").trim();
      }

      function armCommit(interim) {
        if (self._commitTimer) root.clearTimeout(self._commitTimer);
        if ((!hall && !tape) || !interim || lang === "vi") return;
        var wait = Math.max(320, Number(opts.commitMs) || (tape ? 760 : 460));
        self._commitTimer = root.setTimeout(function () {
          self._commitTimer = 0;
          if (!self.listening) return;
          if (!foldEq(self._stableInterim, interim)) return;
          emitFinal(interim);
        }, wait);
      }

      rec.onresult = function (ev) {
        var interim = "";
        var finalText = "";
        var i;
        for (i = ev.resultIndex; i < ev.results.length; i++) {
          var picked = pickResult(ev.results, i, lang);
          if (looksNoisy(picked.confidence, hall, tape) && !picked.fixes) continue;
          if (ev.results[i].isFinal) finalText += (picked.transcript || "") + " ";
          else interim += picked.transcript || "";
        }
        finalText = spaceTrim(finalText);
        interim = spaceTrim(interim);
        if (finalText) emitFinal(finalText);
        if (interim) {
          self._stableInterim = interim;
          armCommit(interim);
        }
        if (opts.onResult) {
          opts.onResult({
            finalText: "",
            interim: repairChunk(interim, lang, tape)
          });
        }
      };
      rec.onerror = function (ev) {
        var code = (ev && ev.error) || "unknown";
        if (code === "no-speech" || code === "aborted" || code === "audio-capture") {
          if (opts.onError && code !== "aborted") opts.onError(code);
          return;
        }
        if (opts.onError) opts.onError(code);
        if (code === "network") return;
        self.listening = false;
      };
      rec.onend = function () {
        if (self._stableInterim && self.listening) {
          emitFinal(self._stableInterim);
        }
        if (self.listening && self.rec === rec) {
          root.setTimeout(function () {
            if (!self.listening || self.rec !== rec) return;
            try {
              rec.start();
            } catch (e) {
              self.listening = false;
              if (opts.onStop) opts.onStop();
            }
          }, tape ? 45 : hall ? 80 : 180);
        } else if (opts.onStop) opts.onStop();
      };
      this.rec = rec;
      this.listening = true;
      try {
        rec.start();
        return true;
      } catch (err) {
        this.listening = false;
        if (opts.onError) opts.onError("start-failed");
        return false;
      }
    },

    _startNative: function (opts) {
      var self = this;
      var plugin = nativeSpeech();
      if (!plugin) {
        if (opts.onError) opts.onError("no-engine");
        return false;
      }
      var tape = !!opts.tape;
      var hall = opts.hall !== false || tape;
      this.desiredLang = localeFor(opts);
      this.listening = true;
      this._nativeInterim = "";
      this._lastFinal = "";
      this._opts = opts;

      function clearRestart() {
        if (self._nativeRestartTimer) {
          root.clearTimeout(self._nativeRestartTimer);
          self._nativeRestartTimer = 0;
        }
      }

      function begin() {
        if (!self.listening) return;
        plugin
          .start({
            language: self.desiredLang,
            maxResults: hall || tape ? 5 : 3,
            partialResults: true,
            popup: false
          })
          .catch(function (err) {
            if (!self.listening) return;
            var code = mapNativeError(err);
            if (code === "no-speech") {
              self._nativeRestartTimer = root.setTimeout(begin, 350);
              return;
            }
            if (opts.onError) opts.onError(code);
            if (code !== "network") self.listening = false;
          });
      }

      function onPartial(data) {
        var matches = (data && data.matches) || [];
        var alts = matches.map(function (m) {
          return { transcript: m, confidence: 0.5 };
        });
        var picked =
          opts.lang !== "vi" && typeof ATC.pickHeardAlternative === "function"
            ? ATC.pickHeardAlternative(alts)
            : { text: String(matches[0] || "").trim() };
        var text = (picked && picked.text) || "";
        if (!text || !self.listening) return;
        self._nativeInterim = text;
        if (opts.onResult) opts.onResult({ finalText: "", interim: text });
      }

      function onState(data) {
        if (!self.listening) return;
        if (!data || data.status !== "stopped") return;
        var committed = self._nativeInterim;
        self._nativeInterim = "";
        if (committed && opts.onResult) {
          var cleaned = repairChunk(committed, opts.lang === "vi" ? "vi" : "en", tape);
          if (typeof ATC.mergeHeardOverlap === "function") {
            var merged = ATC.mergeHeardOverlap(self._lastFinal, cleaned);
            if (merged && merged !== self._lastFinal) {
              self._lastFinal = cleaned;
              opts.onResult({ finalText: cleaned, interim: "" });
            }
          } else {
            opts.onResult({ finalText: cleaned, interim: "" });
          }
        }
        clearRestart();
        self._nativeRestartTimer = root.setTimeout(begin, tape ? 80 : hall ? 160 : 280);
      }

      plugin
        .removeAllListeners()
        .catch(function () {})
        .then(function () {
          return plugin.requestPermissions();
        })
        .then(function (st) {
          var perm = st && st.speechRecognition;
          if (perm && perm !== "granted") {
            throw new Error("not-allowed");
          }
          return plugin.addListener("partialResults", onPartial);
        })
        .then(function () {
          return plugin.addListener("listeningState", onState);
        })
        .then(function () {
          begin();
        })
        .catch(function (err) {
          self.listening = false;
          if (opts.onError) opts.onError(mapNativeError(err));
        });

      return true;
    },

    playTape: function (file, opts) {
      opts = opts || {};
      this.stopTape();
      if (!file) {
        if (opts.onError) opts.onError("tape");
        return false;
      }
      var self = this;
      var url = URL.createObjectURL(file);
      var audio = new Audio();
      audio.src = url;
      audio.preload = "auto";
      var rate = Number(opts.rate);
      if (!isFinite(rate) || rate <= 0) rate = 0.85;
      audio.playbackRate = Math.max(0.7, Math.min(1.05, rate));
      if ("preservesPitch" in audio) audio.preservesPitch = true;
      if ("mozPreservesPitch" in audio) audio.mozPreservesPitch = true;
      var Ctx = root.AudioContext || root.webkitAudioContext;
      var ctx = Ctx ? new Ctx() : null;
      if (ctx) {
        try {
          var src = ctx.createMediaElementSource(audio);
          var hp = ctx.createBiquadFilter();
          hp.type = "highpass";
          hp.frequency.value = 150;
          hp.Q.value = 0.7;
          var notch = ctx.createBiquadFilter();
          notch.type = "peaking";
          notch.frequency.value = 3800;
          notch.Q.value = 0.9;
          notch.gain.value = -8;
          var lp = ctx.createBiquadFilter();
          lp.type = "lowpass";
          lp.frequency.value = 5800;
          var comp = ctx.createDynamicsCompressor();
          comp.threshold.value = -22;
          comp.knee.value = 18;
          comp.ratio.value = 3.5;
          comp.attack.value = 0.008;
          comp.release.value = 0.18;
          src.connect(hp);
          hp.connect(notch);
          notch.connect(lp);
          lp.connect(comp);
          comp.connect(ctx.destination);
          if (ctx.state === "suspended" && ctx.resume) ctx.resume();
        } catch (e) {
          ctx = null;
        }
      }
      this._tape = { audio: audio, url: url, ctx: ctx };
      audio.onended = function () {
        self.stopTape({ ended: true });
        if (opts.onEnded) opts.onEnded();
      };
      audio.onerror = function () {
        if (opts.onError) opts.onError("tape");
      };
      var play = audio.play();
      if (play && play.catch) {
        play.catch(function () {
          if (opts.onError) opts.onError("tape");
        });
      }
      return true;
    },

    stopTape: function () {
      var t = this._tape;
      this._tape = null;
      if (!t) return;
      try {
        t.audio.onended = null;
        t.audio.onerror = null;
        t.audio.pause();
      } catch (e) {}
      try {
        t.audio.removeAttribute("src");
        t.audio.load();
      } catch (e2) {}
      try {
        URL.revokeObjectURL(t.url);
      } catch (e3) {}
      if (t.ctx) {
        try {
          t.ctx.close();
        } catch (e4) {}
      }
    },

    tapePlaying: function () {
      return !!(this._tape && this._tape.audio && !this._tape.audio.paused);
    },

    stop: function (opts) {
      opts = opts || {};
      this.listening = false;
      if (!opts.keepTape) this.stopTape();
      if (this._nativeRestartTimer) {
        root.clearTimeout(this._nativeRestartTimer);
        this._nativeRestartTimer = 0;
      }
      if (this._commitTimer) {
        root.clearTimeout(this._commitTimer);
        this._commitTimer = 0;
      }
      this._stableInterim = "";
      var plugin = nativeSpeech();
      if (plugin) {
        try {
          plugin.stop();
        } catch (e) {}
        try {
          plugin.removeAllListeners();
        } catch (e2) {}
      }
      if (this.rec) {
        try {
          this.rec.onend = null;
          this.rec.stop();
        } catch (e3) {}
      }
      this.rec = null;
    },

    speak: function (text, opts) {
      opts = opts || {};
      if (!this.ttsAvailable()) {
        if (opts.onError) opts.onError("no-tts");
        return;
      }
      root.speechSynthesis.cancel();
      var u = new root.SpeechSynthesisUtterance(String(text || ""));
      u.lang = opts.lang || "en-GB";
      u.rate = opts.rate || 0.92;
      u.pitch = 1;
      var voices = root.speechSynthesis.getVoices() || [];
      var want = voices.filter(function (v) {
        return (v.lang || "").toLowerCase().indexOf((u.lang || "en").slice(0, 2)) === 0;
      });
      if (want.length) {
        var gb = want.filter(function (v) {
          return /en-GB|en_GB|English United Kingdom/i.test(v.lang + v.name);
        });
        u.voice = (opts.lang || "").indexOf("en") === 0 && gb.length ? gb[0] : want[0];
      }
      if (opts.onend) u.onend = opts.onend;
      if (opts.onError) u.onerror = function () { opts.onError("tts"); };
      root.speechSynthesis.speak(u);
    },

    silence: function () {
      if (root.speechSynthesis) root.speechSynthesis.cancel();
    }
  };

  if (root.speechSynthesis && root.speechSynthesis.getVoices) {
    root.speechSynthesis.getVoices();
    if (typeof root.speechSynthesis.onvoiceschanged !== "undefined") {
      root.speechSynthesis.onvoiceschanged = function () {
        root.speechSynthesis.getVoices();
      };
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
