const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/js/recordings.js'), 'utf8');
const poll = source.slice(source.indexOf('  function pollConvertJob('), source.indexOf('  function needsServerTranscode('));

function mockXHR(alwaysFail, state) {
  return function XMLHttpRequest() {
    this.open = function () {};
    this.send = function () {
      state.downloads += 1;
      const req = this;
      queueMicrotask(() => {
        if (alwaysFail || state.downloads === 1) {
          if (typeof req.onerror === 'function') req.onerror();
          return;
        }
        req.status = 200;
        req.response = new Blob(['complete mp4']);
        req.getResponseHeader = () => 'video/mp4';
        if (typeof req.onload === 'function') req.onload();
      });
    };
  };
}

async function check(alwaysFail) {
  const state = { downloads: 0 };
  const context = {
    Date, Promise, Blob, encodeURIComponent, Math,
    setConvertProgress() {}, hideConvertModal() {},
    formatBytes: n => String(n),
    setTimeout: callback => callback(),
    fetch: async url => {
      if (url.includes('/status?')) return { json: async () => ({done: true, duration: 12}) };
      throw new Error('result should use XHR');
    },
    XMLHttpRequest: mockXHR(alwaysFail, state)
  };
  vm.createContext(context);
  vm.runInContext(poll, context);
  const result = new Promise((resolve, reject) => context.pollConvertJob('same-job', 100, resolve, reject));
  if (alwaysFail) {
    await assert.rejects(result, /Kết nối bị ngắt khi tải MP4|Không tải được file MP4/);
    assert.equal(state.downloads, 5);
  } else {
    const out = await result;
    assert.equal(out.duration, 12);
    assert.equal(state.downloads, 2);
    assert.equal(out.blob.size, 'complete mp4'.length);
  }
}
check(false).then(() => check(true)).then(() => console.log('MP4 download retry and retry limit passed'));
