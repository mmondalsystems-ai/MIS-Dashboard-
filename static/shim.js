// Makes google.script.run work against the Python server.
// The page code (withSuccessHandler / withFailureHandler / fn(...)) stays unchanged.
(function () {
  function makeRunner(ok, fail) {
    return new Proxy({}, {
      get: function (_, name) {
        if (name === 'withSuccessHandler') return function (f) { return makeRunner(f, fail); };
        if (name === 'withFailureHandler') return function (f) { return makeRunner(ok, f); };
        if (name === 'withUserObject') return function () { return makeRunner(ok, fail); };
        return function () {
          var args = Array.prototype.slice.call(arguments);
          fetch('/api/' + String(name), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ args: args })
          }).then(function (r) { return r.json(); }).then(function (j) {
            if (j.ok) { if (ok) ok(j.result); }
            else if (fail) fail({ message: j.error });
            else console.error(j.error);
          }).catch(function (e) { if (fail) fail(e); else console.error(e); });
        };
      }
    });
  }
  window.google = { script: { run: makeRunner(null, null) } };
})();
