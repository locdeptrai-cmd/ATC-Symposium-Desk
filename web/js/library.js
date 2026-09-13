(function (root) {
  'use strict';
  var ATC = root.ATC || (root.ATC = {}), data = root.ATC_LIBRARY;
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/\s+/g, ' ').trim(); }
  var indexed = data.entries.map(function (r) { return {row:r, text:norm([r.abbr,r.en,r.vi,r.note].join(' '))}; });
  ATC.library = {data:data, search:function (query, domain, kind) {
    var q = norm(query), tokens = q.split(' ').filter(Boolean);
    function score(r) { return (q && [r.abbr,r.en,r.vi].some(function (v) {return norm(v)===q;}) ? 100 : 0) + (r.source==='vn19' ? 20 : r.source==='editor' ? 19 : r.source==='doc4444' ? 18 : r.source==='aipvn' ? 17 : r.source==='icao8585' ? 17 : r.source==='vatm' ? 16 : ['editorial','pbn'].includes(r.source) ? 15 : r.source==='legacy' ? 5 : 0); }
    return indexed.filter(function (i) { return (!domain || i.row.domain===domain) && (!kind || i.row.kind===kind) && tokens.every(function (t) {return i.text.includes(t);}); }).map(function (i) {return i.row;}).sort(function (a,b) {return score(b)-score(a) || a.en.localeCompare(b.en);});
  }};
  var curated = data.entries.filter(function (r) {return !['general','legacy'].includes(r.domain);});
  var keys = new Set(curated.map(function (r) {return norm(r.en);}));
  ATC.TERMS = curated.filter(function (r) {return r.kind==='term';}).concat((ATC.TERMS || []).filter(function (r) {return !keys.has(norm(r.en));}));
  ATC.PHRASES = curated.filter(function (r) {return r.kind==='sentence';}).concat((ATC.PHRASES || []).filter(function (r) {return !keys.has(norm(r.en));}));
  var exact = {en:new Map(), vi:new Map()};
  function key(s) {return String(s).toLowerCase().replace(/[’‘]/g,"'").replace(/[.!?]+$/g,'').replace(/\s+/g,' ').trim();}
  curated.forEach(function (r) {exact.en.set(key(r.en),r); exact.vi.set(key(r.vi),r);});
  ATC.library.exact = function (text,source) {return exact[source] && exact[source].get(key(text));};
  ATC.library.ingest = function (rows) {
    if (!rows || !rows.length) return;
    var have = new Set(data.entries.map(function (r) { return r.id; }));
    rows.forEach(function (r) {
      if (!r || !r.en || !r.vi || have.has(r.id)) return;
      have.add(r.id);
      data.entries.push(r);
      indexed.push({ row: r, text: norm([r.abbr, r.en, r.vi, r.note].join(' ')) });
      if (!['general', 'legacy'].includes(r.domain)) {
        exact.en.set(key(r.en), r);
        exact.vi.set(key(r.vi), r);
      }
    });
  };
  ATC.library.remove = function (id) {
    data.entries = data.entries.filter(function (r) { return r.id !== id; });
    indexed = indexed.filter(function (i) { return i.row.id !== id; });
  };
})(globalThis);
