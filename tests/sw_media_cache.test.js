const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const handlers = {};
const context = {
  URL,
  self: {
    location: { origin: 'http://127.0.0.1:8767' },
    addEventListener: (name, callback) => { handlers[name] = callback; }
  },
  caches: { match: () => Promise.resolve('cached asset') }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/sw.js'), 'utf8'), context);
for (const route of ['/api/media/transcode/status?id=one', '/api/media/transcode/result?id=two']) {
  handlers.fetch({
    request: { method: 'GET', url: context.self.location.origin + route },
    respondWith: () => { throw new Error('Media API must bypass the offline cache'); }
  });
}
let intercepted = false;
handlers.fetch({
  request: { method: 'GET', url: context.self.location.origin + '/js/recordings.js' },
  respondWith: () => { intercepted = true; }
});
assert.ok(intercepted, 'Static assets should remain available offline');
console.log('Media API cache bypass passed');
