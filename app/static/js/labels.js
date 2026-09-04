/* Shrink each label's name until the whole word fits its box. Runs once the
   font has loaded, otherwise it measures the fallback font and gets it wrong. */
(function () {
  function fit() {
    document.querySelectorAll('.label .name').forEach(function (box) {
      var span = box.querySelector('span');
      var size = 12;
      span.style.fontSize = size + 'pt';
      while (size > 4 && (span.scrollWidth > box.clientWidth || span.scrollHeight > box.clientHeight)) {
        size -= 0.5; span.style.fontSize = size + 'pt';
      }
    });
  }
  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(fit); } else { fit(); }
  window.addEventListener('beforeprint', fit);
})();
