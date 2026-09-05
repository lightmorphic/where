/* Fit each label's name to its box. One line reads best on a small label, so
   try that first and only allow wrapping when a single line would be too small
   to read across the room. Runs after the font has loaded, otherwise it
   measures the fallback font and gets the size wrong. */
(function () {
  var MAX = 12, MIN_ONE_LINE = 6.5, MIN = 4.5;

  function fits(span, box) {
    return span.scrollWidth <= box.clientWidth && span.scrollHeight <= box.clientHeight;
  }

  function fit() {
    document.querySelectorAll('.label .name').forEach(function (box) {
      var span = box.querySelector('span');
      var size = MAX;

      // One line, as large as will fit.
      span.style.whiteSpace = 'nowrap';
      span.style.fontSize = size + 'pt';
      while (size > MIN_ONE_LINE && !fits(span, box)) {
        size -= 0.25; span.style.fontSize = size + 'pt';
      }
      if (fits(span, box)) { return; }

      // Too long for one line at a readable size, so let it wrap instead.
      span.style.whiteSpace = 'normal';
      size = MAX;
      span.style.fontSize = size + 'pt';
      while (size > MIN && !fits(span, box)) {
        size -= 0.25; span.style.fontSize = size + 'pt';
      }
    });
  }

  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(fit); } else { fit(); }
  window.addEventListener('beforeprint', fit);
})();
