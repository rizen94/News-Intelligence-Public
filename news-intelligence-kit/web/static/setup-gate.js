(function () {
  if (window.location.pathname.startsWith('/setup')) return;
  fetch('/api/setup/status')
    .then(function (r) { return r.json(); })
    .then(function (s) {
      if (s && s.setup_complete === false) {
        window.location.replace('/setup/');
      }
    })
    .catch(function () {});
})();
