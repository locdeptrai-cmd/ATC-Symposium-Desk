(function () {
  "use strict";
  var DB_NAME = "atc-glossary-editor";
  var STORE = "entries";
  var API = "/api/library/user";
  var rows = [];

  function $(id) {
    return document.getElementById(id);
  }

  function norm(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .replace(/\s+/g, " ")
      .trim();
  }

  function makeId(en, vi) {
    var key = norm(en) + "\t" + norm(vi) + "\teditor";
    var h = 2166136261;
    for (var i = 0; i < key.length; i++) {
      h ^= key.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return "ed" + (h >>> 0).toString(16);
  }

  function asEntry(raw) {
    var en = String(raw.en || "").trim();
    var vi = String(raw.vi || "").trim();
    if (!en || !vi) return null;
    var kind = raw.kind === "sentence" || /[.?!]$/.test(en) ? "sentence" : "term";
    return {
      id: String(raw.id || makeId(en, vi)),
      abbr: String(raw.abbr || "").trim().slice(0, 24),
      en: en.slice(0, 240),
      vi: vi.slice(0, 240),
      note: String(raw.note || "").trim().slice(0, 500),
      domain: "editor",
      source: "editor",
      kind: kind,
      status: "unreviewed"
    };
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        if (!req.result.objectStoreNames.contains(STORE)) {
          req.result.createObjectStore(STORE, { keyPath: "id" });
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

  function idbAll() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
        req.onsuccess = function () {
          resolve(req.result || []);
        };
        req.onerror = function () {
          reject(req.error);
        };
      });
    });
  }

  function idbPut(entry) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put(entry);
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function idbDelete(id) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).delete(id);
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function merge(list) {
    var map = new Map(rows.map(function (r) { return [r.id, r]; }));
    (list || []).forEach(function (raw) {
      var e = asEntry(raw);
      if (e) map.set(e.id, e);
    });
    rows = Array.from(map.values()).sort(function (a, b) {
      return a.en.localeCompare(b.en);
    });
    if (ATC.library && ATC.library.ingest) ATC.library.ingest(rows);
    if (ATC.glossaryUI && ATC.glossaryUI.render) ATC.glossaryUI.render(true);
    paint();
  }

  function paint() {
    var body = $("edRows");
    if (!body) return;
    body.replaceChildren();
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      [r.abbr, r.en, r.vi].forEach(function (v) {
        var td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      var td = document.createElement("td");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost";
      btn.textContent = "Xóa";
      btn.onclick = function () {
        remove(r.id);
      };
      td.appendChild(btn);
      tr.appendChild(td);
      body.appendChild(tr);
    });
    var count = $("edCount");
    if (count) count.textContent = rows.length + " mẫu nhập tay";
  }

  function msg(text, ok) {
    var el = $("edMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = ok ? "var(--ok)" : "var(--amber)";
  }

  function persistServer() {
    return fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: rows })
    }).then(function (res) {
      return res.json().then(function (payload) {
        if (!res.ok || payload.ok === false) throw new Error(payload.error || "Không lưu được lên máy chủ.");
        return payload;
      });
    });
  }

  function save() {
    var entry = asEntry({
      abbr: $("edAbbr").value,
      en: $("edEn").value,
      vi: $("edVi").value,
      note: $("edNote").value,
      kind: $("edKind").value
    });
    if (!entry) {
      msg("Cần nhập English và tiếng Việt.");
      return;
    }
    var dup = rows.some(function (r) {
      return r.id === entry.id || (norm(r.en) === norm(entry.en) && norm(r.vi) === norm(entry.vi));
    });
    if (dup) {
      msg("Mẫu này đã có trong editor.");
      return;
    }
    idbPut(entry)
      .then(function () {
        merge([entry]);
        return persistServer().catch(function () {
          return null;
        });
      })
      .then(function () {
        msg("Đã thêm. Lọc chuyên đề Editor để xem.", true);
        $("edEn").value = "";
        $("edVi").value = "";
        $("edNote").value = "";
        $("edAbbr").value = "";
      })
      .catch(function (err) {
        msg(err.message || "Không lưu được.");
      });
  }

  function remove(id) {
    idbDelete(id)
      .then(function () {
        rows = rows.filter(function (r) { return r.id !== id; });
        if (ATC.library && ATC.library.remove) ATC.library.remove(id);
        if (ATC.glossaryUI && ATC.glossaryUI.render) ATC.glossaryUI.render(true);
        paint();
        return persistServer().catch(function () {
          return null;
        });
      })
      .then(function () {
        msg("Đã xóa mẫu.", true);
      })
      .catch(function (err) {
        msg(err.message || "Không xóa được.");
      });
  }

  function load() {
    Promise.all([
      idbAll().catch(function () { return []; }),
      fetch(API, { cache: "no-store" })
        .then(function (res) { return res.ok ? res.json() : { entries: [] }; })
        .then(function (payload) { return payload.entries || []; })
        .catch(function () { return []; })
    ]).then(function (pair) {
      merge(pair[0].concat(pair[1]));
    });
  }

  $("edSave").addEventListener("click", save);
  $("edClear").addEventListener("click", function () {
    $("edAbbr").value = "";
    $("edEn").value = "";
    $("edVi").value = "";
    $("edNote").value = "";
    msg("");
  });
  load();
})();
