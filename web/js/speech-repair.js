(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  var CONTEXT = /\b(sms|frms|atfm|pbn|rnav|rnp|swim|icao|ansp|atco|atsep|notam|aip|ads-?b|cpdlc|fir|tma|acc|app|sid|star|cdo|cco|aman|dman|a-?cdm|rvsm|cbta|fatigue|safety|capacity|airspace|runway|controller|pilot|traffic|sector|roster|duty|squawk|cleared|wilco|roger|affirm|qnh|taxi|tower)\b/i;

  var MISHEAR = [
    { re: /\bf[\s.\-]*r[\s.\-]*m[\s.\-]*s\b/gi, to: "FRMS", always: true },
    { re: /\bp[\s.\-]*b[\s.\-]*n\b/gi, to: "PBN", always: true },
    { re: /\ba[\s.\-]*t[\s.\-]*f[\s.\-]*m\b/gi, to: "ATFM", always: true },
    { re: /\bs[\s.\-]*m[\s.\-]*s\b/gi, to: "SMS", always: true },
    { re: /\bi[\s.\-]*c[\s.\-]*a[\s.\-]*o\b/gi, to: "ICAO", always: true },
    { re: /\ba[\s.\-]*t[\s.\-]*c[\s.\-]*o\b/gi, to: "ATCO", always: true },
    { re: /\ba[\s.\-]*t[\s.\-]*s\b/gi, to: "ATS", always: true },
    { re: /\ba[\s.\-]*t[\s.\-]*m\b/gi, to: "ATM", always: true },
    { re: /\ba[\s.\-]*n[\s.\-]*s[\s.\-]*p\b/gi, to: "ANSP", always: true },
    { re: /\ba[\s.\-]*d[\s.\-]*s[\s.\-]*b\b/gi, to: "ADS-B", always: true },
    { re: /\bc[\s.\-]*p[\s.\-]*d[\s.\-]*l[\s.\-]*c\b/gi, to: "CPDLC", always: true },
    { re: /\br[\s.\-]*v[\s.\-]*s[\s.\-]*m\b/gi, to: "RVSM", always: true },
    { re: /\ba[\s.\-]*c[\s.\-]*d[\s.\-]*m\b/gi, to: "A-CDM", always: true },
    { re: /\bc[\s.\-]*d[\s.\-]*o\b/gi, to: "CDO", always: true },
    { re: /\bc[\s.\-]*c[\s.\-]*o\b/gi, to: "CCO", always: true },
    { re: /\b(?:ice|eye)\s*cows?\b/gi, to: "ICAO", always: true },
    { re: /\bi\s*kay\s*o\b/gi, to: "ICAO", always: true },
    { re: /\bno(?:\s+|-)tams?\b/gi, to: "NOTAM", always: true },
    { re: /\bnote\s+ams?\b/gi, to: "NOTAM", always: true },
    { re: /\bads[\s\-]*bees?\b/gi, to: "ADS-B", always: true },
    { re: /\bat[\s\-]*fm\b/gi, to: "ATFM", always: true },
    { re: /\beat[\s\-]*fm\b/gi, to: "ATFM", always: true },
    { re: /\bat[\s\-]*co(?:s)?\b/gi, to: "ATCO", always: true },
    { re: /\bat[\s\-]*sep\b/gi, to: "ATSEP", always: true },
    { re: /\bsee\s*p\s*d\s*l\s*c\b/gi, to: "CPDLC", always: true },
    { re: /\bfirms?\b/gi, to: "FRMS", always: false },
    { re: /\bfarms?\b/gi, to: "FRMS", always: false },
    { re: /\bframe\s*s\b/gi, to: "FRMS", always: false },
    { re: /\bswim\b/gi, to: "SWIM", always: false },
    { re: /\ba\s+man\b/gi, to: "AMAN", always: false },
    { re: /\bdee\s+man\b/gi, to: "DMAN", always: false },
    { re: /\bsquark\b/gi, to: "squawk", always: true },
    { re: /\bsquawk\s+ident\b/gi, to: "squawk ident", always: true },
    { re: /\bline\s+up\s+and\s+weight\b/gi, to: "line up and wait", always: true },
    { re: /\bgo\s+a\s*round\b/gi, to: "go around", always: true },
    { re: /\bhold\s+short\b/gi, to: "hold short", always: true },
    { re: /\bcleared\s+to\s+land\b/gi, to: "cleared to land", always: true },
    { re: /\bcleared\s+for\s+take[\s\-]*off\b/gi, to: "cleared for take-off", always: true },
    { re: /\bcontact\s+tower\b/gi, to: "contact tower", always: true },
    { re: /\bcontact\s+approach\b/gi, to: "contact approach", always: true },
    { re: /\bwill\s+co\b/gi, to: "wilco", always: true },
    { re: /\bq\.?\s*n\.?\s*h\.?\b/gi, to: "QNH", always: true },
    { re: /\b(?:charlie|charley)\s+jet\b/gi, to: "Vietjet", always: true },
    { re: /\bvee+\s*jet\b/gi, to: "Vietjet", always: true },
    { re: /\bviet\s*jet(?:\s+air)?\b/gi, to: "Vietjet", always: true },
    { re: /\bvietjetair\b/gi, to: "Vietjet", always: true },
    { re: /\bviet\s*nam(?:\s+airlines?)?\b/gi, to: "Viet Nam", always: true },
    { re: /\bvietnam(?:\s+airlines?)?\b/gi, to: "Viet Nam", always: true },
    { re: /\bsai\s*gon\s+tower\b/gi, to: "TSN Tower", always: true },
    { re: /\bsona\s+tower\b/gi, to: "TSN Tower", always: true },
    { re: /\bsaigon\s+tower\b/gi, to: "TSN Tower", always: true },
    { re: /\btan\s+son\s+nhat\b/gi, to: "Tan Son Nhat", always: true },
    { re: /\bnoy?\s*bai(?:\s+tower)?\b/gi, to: "Noi Bai", always: true },
    { re: /\bnoibai\b/gi, to: "Noi Bai", always: true },
    { re: /\blater\s+to\s+land\b/gi, to: "cleared to land", always: true },
    { re: /\bcontinue\s+approach\s+over\s+to\s+ukraine\b/gi, to: "continue approach", always: true },
    { re: /\bsion\s+(?=one|two|three|four|five)/gi, to: "Vietjet ", always: true },
    { re: /\b(?:qi|qq)\s+nine(?:\s+zero)?\s+nine\b/gi, to: "Viet Nam nine zero nine", always: true },
    { re: /\btwo\s+fellay\b/gi, to: "two five", always: true },
    { re: /\bfellay\b/gi, to: "five", always: true },
    { re: /\brunway\s+two\s+final\b/gi, to: "runway two five", always: true },
    { re: /\bniner\b/gi, to: "nine", always: true },
    { re: /\bfife\b/gi, to: "five", always: true }
  ];

  function spaceNorm(s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  function fold(s) {
    return spaceNorm(s)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d");
  }

  function abbrIndex() {
    var map = {};
    (ATC.TERMS || []).forEach(function (t) {
      var abbr = String(t.abbr || t.enDisplay || "").trim();
      if (!abbr || abbr.length < 2 || abbr.length > 10) return;
      map[abbr.replace(/[^A-Za-z0-9]/g, "").toLowerCase()] = abbr;
    });
    [
      "FRMS", "PBN", "ATFM", "SMS", "ICAO", "ATCO", "ATSEP", "ANSP", "ATS", "ATM",
      "ADS-B", "ADS-C", "CPDLC", "NOTAM", "AIP", "FIR", "TMA", "ACC", "APP",
      "SID", "STAR", "CDO", "CCO", "AMAN", "DMAN", "A-CDM", "RVSM", "SWIM",
      "CBTA", "OJT", "OJTI", "QNH", "QFE", "METAR", "TAF", "SIGMET"
    ].forEach(function (a) {
      var k = a.replace(/[^A-Za-z0-9]/g, "").toLowerCase();
      if (!map[k]) map[k] = a;
    });
    return map;
  }

  function joinSpelled(text, index) {
    return text.replace(/\b[a-zA-Z](?:[\s.\-\/]+[a-zA-Z]){1,7}\b/g, function (chunk) {
      var key = chunk.replace(/[^A-Za-z0-9]/g, "").toLowerCase();
      return index[key] || chunk;
    });
  }

  function applyMishear(text, aviation) {
    var fixes = [];
    MISHEAR.forEach(function (row) {
      if (!row.always && !aviation) return;
      var next = text.replace(row.re, function (m) {
        if (m.toUpperCase() === row.to) return m;
        fixes.push(row.to);
        return row.to;
      });
      text = next;
    });
    return { text: text, fixes: fixes };
  }

  var COMMON = (
    "the of and to in for is that this with from not on at by as be or an are was were been have has had will would can could should must " +
    "we you they it unit put inside just only also more than into about after before over under between through during without within " +
    "then now so if when what which who how there their them these those our your may might need needs needed take taken taking " +
    "make made making give given said say says discuss discussed discussion safety capacity traffic flight air space control " +
    "manage management system systems service services information data implement implementation operational operations " +
    "procedure procedures question point floor thank chair distinguished speaker ladies gentlemen today thank you very much"
  ).split(/\s+/);

  var STATIC_JUNK = /^(uh+|u+m+|er+|ah+|oh+|hmm+|mhm+|shh+|sss+|xxx+|tsk+|huh+|mm+|huh|erm)$/i;

  function wordLex() {
    var lex = {};
    COMMON.forEach(function (w) {
      if (w) lex[w.toLowerCase()] = w.toLowerCase();
    });
    (ATC.TERMS || []).forEach(function (t) {
      String(t.en || "")
        .split(/[^A-Za-z0-9]+/)
        .forEach(function (w) {
          var key = w.toLowerCase();
          if (w.length >= 3 && !lex[key]) lex[key] = key;
        });
    });
    var idx = abbrIndex();
    Object.keys(idx).forEach(function (k) {
      lex[k] = idx[k];
    });
    return lex;
  }

  function stripStaticJunk(text) {
    var words = String(text || "").split(/\s+/);
    return words
      .filter(function (w, i) {
        if (!w) return false;
        if (STATIC_JUNK.test(w)) return false;
        if (/^[^A-Za-z0-9]+$/.test(w)) return false;
        if (w.length === 1 && !/^[ai]$/i.test(w)) {
          var prev = words[i - 1] || "";
          var next = words[i + 1] || "";
          return /^[A-Za-z]$/.test(prev) || /^[A-Za-z]$/.test(next);
        }
        return true;
      })
      .join(" ");
  }

  function collapseStutter(text) {
    return spaceNorm(
      text
        .replace(/\b([A-Za-z0-9]{1,12})(?:\s+\1){2,}\b/gi, "$1")
        .replace(/\b([A-Za-z]{2,20})\s+\1\b/gi, "$1")
    );
  }

  function segmentGlued(tok, lex) {
    var raw = String(tok || "").replace(/[^A-Za-z0-9]/g, "");
    if (raw.length < 8) return "";
    var s = raw.toLowerCase();
    var parts = [];
    var i = 0;
    while (i < s.length) {
      var found = "";
      var foundLen = 0;
      var len;
      for (len = Math.min(28, s.length - i); len >= 2; len--) {
        var piece = s.slice(i, i + len);
        if (lex[piece]) {
          found = lex[piece];
          foundLen = len;
          break;
        }
      }
      if (!found) return "";
      parts.push(found);
      i += foundLen;
    }
    return parts.length > 1 ? parts.join(" ") : "";
  }

  function splitGluedAcronyms(text, index) {
    var names = Object.keys(index)
      .filter(function (k) {
        return k.length >= 2;
      })
      .sort(function (a, b) {
        return b.length - a.length;
      });
    var out = text;
    names.forEach(function (k) {
      var disp = index[k];
      var esc = disp.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      out = out.replace(new RegExp("([a-z]{2,})(" + esc + ")(?=[A-Za-z]|$)", "g"), "$1 $2");
      out = out.replace(new RegExp("(" + esc + ")([a-z]{2,})", "g"), "$1 $2");
    });
    return out;
  }

  function unstickText(text) {
    var lex = wordLex();
    return text
      .split(/(\s+)/)
      .map(function (tok) {
        if (/^\s+$/.test(tok) || tok.length < 8) return tok;
        return segmentGlued(tok, lex) || tok;
      })
      .join("");
  }

  function termHits(text) {
    var found = [];
    var low = fold(text);
    var seen = {};
    (ATC.TERMS || []).forEach(function (t) {
      var abbr = String(t.abbr || "").trim();
      var en = String(t.en || "").trim();
      if (abbr && abbr.length >= 2 && new RegExp("\\b" + abbr.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i").test(text)) {
        if (!seen[abbr]) {
          seen[abbr] = true;
          found.push(abbr);
        }
        return;
      }
      if (en && en.length > 4 && low.indexOf(fold(en)) >= 0) {
        var label = abbr || en;
        if (!seen[label]) {
          seen[label] = true;
          found.push(label);
        }
      }
    });
    return found;
  }

  ATC.repairHeard = function (text, lang, opts) {
    var raw = spaceNorm(text);
    opts = opts || {};
    if (!raw) return { text: "", fixes: [], terms: [] };
    if (lang === "vi") return { text: raw, fixes: [], terms: termHits(raw) };
    var index = abbrIndex();
    var cleaned = stripStaticJunk(raw);
    cleaned = spaceNorm(unstickText(cleaned));
    cleaned = splitGluedAcronyms(cleaned, index);
    var joined = joinSpelled(cleaned, index);
    var aviation = CONTEXT.test(joined) || CONTEXT.test(raw);
    var mis = applyMishear(joined, aviation);
    var out = collapseStutter(spaceNorm(mis.text));
    var fixes = [];
    mis.fixes.forEach(function (f) {
      if (fixes.indexOf(f) < 0) fixes.push(f);
    });
    if (fold(cleaned) !== fold(raw)) fixes.push("static");
    if (fold(joined) !== fold(cleaned)) fixes.push("spelling");
    if (fold(out) !== fold(mis.text)) fixes.push("unstick");
    if (opts.tape && !fixes.length && fold(out) !== fold(raw)) fixes.push("tape");
    return { text: out, fixes: fixes, terms: termHits(out) };
  };

  ATC.scoreHeardAlternative = function (alt) {
    var text = spaceNorm(alt && alt.transcript);
    var conf = Number(alt && alt.confidence);
    if (!isFinite(conf)) conf = 0.45;
    var repaired = ATC.repairHeard(text, "en");
    var words = text ? text.split(/\s+/).length : 0;
    return (
      conf * 80 +
      repaired.terms.length * 8 +
      repaired.fixes.length * 3 +
      Math.min(words, 18) * 0.4
    );
  };

  ATC.pickHeardAlternative = function (alts) {
    var list = (alts || []).filter(function (a) {
      return a && spaceNorm(a.transcript);
    });
    if (!list.length) return null;
    list.sort(function (a, b) {
      return ATC.scoreHeardAlternative(b) - ATC.scoreHeardAlternative(a);
    });
    var best = list[0];
    var repaired = ATC.repairHeard(best.transcript, "en");
    return {
      text: repaired.text,
      raw: spaceNorm(best.transcript),
      confidence: Number(best.confidence) || 0,
      fixes: repaired.fixes,
      terms: repaired.terms
    };
  };

  ATC.mergeHeardOverlap = function (prev, next) {
    var a = spaceNorm(prev);
    var b = spaceNorm(next);
    if (!b) return a;
    if (!a) return b;
    var fa = fold(a);
    var fb = fold(b);
    if (fb.indexOf(fa) === 0) return b;
    if (fa.indexOf(fb) >= 0) return a;
    if (fa.length >= 12 && fb.length >= 8 && fa.indexOf(fb) >= 0) return a;
    if (fb.length >= 12 && fa.length >= 8 && fb.indexOf(fa) >= 0) return b;
    var aWords = a.split(" ");
    var max = Math.min(12, aWords.length, b.split(" ").length);
    var n;
    for (n = max; n >= 2; n--) {
      var tail = fold(aWords.slice(-n).join(" "));
      if (fb.indexOf(tail) === 0) {
        return spaceNorm(aWords.slice(0, -n).join(" ") + " " + b);
      }
    }
    return spaceNorm(a + " " + b);
  };

  ATC.heardBrief = function (text) {
    var pack = ATC.repairHeard(text, "en");
    var terms = (pack.terms || []).slice(0, 4);
    if (!terms.length) return "";
    return "The point on the floor concerns " + terms.join(", ") + ".";
  };

  ATC.grammarFromTerms = function () {
    var parts = [];
    var seen = {};
    (ATC.TERMS || []).forEach(function (t) {
      var abbr = String(t.abbr || "").replace(/[^A-Za-z0-9]/g, "");
      if (abbr.length < 2 || abbr.length > 8 || seen[abbr]) return;
      seen[abbr] = true;
      parts.push(abbr);
    });
    if (!parts.length) {
      parts = ["PBN", "FRMS", "ATFM", "SWIM", "SMS", "ICAO", "ATCO", "NOTAM", "ADS", "CPDLC"];
    }
    return "#JSGF V1.0; grammar atc; public <term> = " + parts.slice(0, 80).join(" | ") + " ;";
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
