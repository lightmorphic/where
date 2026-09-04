/* Shrink each label's name until it fits its box. */
(function () {
  document.querySelectorAll('.label .name').forEach(function (box) {
    var span = box.querySelector('span');
    var size = 12;
    span.style.fontSize = size + 'pt';
    while (size > 5 && (span.scrollHeight > box.clientHeight || span.scrollWidth > box.clientWidth)) {
      size -= 0.5; span.style.fontSize = size + 'pt';
    }
  });
})();
