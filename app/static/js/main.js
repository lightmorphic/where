/* Where - small helpers shared by every page. No build step. */
window.Where = (function () {
  'use strict';

  // Two-press delete: first press arms the button, second press submits.
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.two-step');
    if (!b) return;
    if (b.classList.contains('armed')) return; // second press: let it submit
    e.preventDefault();
    var label = b.textContent;
    b.classList.add('armed');
    b.textContent = b.dataset.confirm || 'Press again to confirm';
    setTimeout(function () { b.classList.remove('armed'); b.textContent = label; }, 4000);
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(function () {});
  }

  function photoPreview(inputId, imgId, dropId) {
    var input = document.getElementById(inputId), img = document.getElementById(imgId), drop = document.getElementById(dropId);
    if (!input || !img) return;
    input.addEventListener('change', function () {
      var f = input.files && input.files[0];
      if (!f) return;
      var url = URL.createObjectURL(f);
      img.src = url; img.hidden = false; drop.classList.add('has-photo');
      var cta = drop.querySelector('.photo-cta span:not(.hint)');
      if (cta) cta.textContent = 'Retake photo';
    });
  }

  function goneSwitch(id) {
    var sw = document.getElementById(id);
    if (!sw) return;
    sw.addEventListener('change', function () {
      fetch(sw.dataset.url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gone: sw.checked })
      }).then(function (r) { if (!r.ok) throw new Error(); location.reload(); })
        .catch(function () { sw.checked = !sw.checked; });
    });
  }

  // While the model is still describing, poll until the text arrives.
  function watchDescription(formId, textareaId, statusId) {
    var form = document.getElementById(formId);
    if (!form || form.dataset.status !== 'pending') return;
    var ta = document.getElementById(textareaId), status = document.getElementById(statusId);
    var touched = false;
    ta.addEventListener('input', function () { touched = true; });
    var tries = 0;
    (function poll() {
      if (tries++ > 150) { status.textContent = 'Still waiting. Check back later.'; return; }
      setTimeout(function () {
        fetch('/api/items/' + form.dataset.item).then(function (r) { return r.json(); }).then(function (d) {
          if (d.desc_status === 'pending') return poll();
          if (d.desc_status === 'done' && !touched && d.description) { ta.value = d.description; status.textContent = '✓ Written from the photo. Edit it if you like.'; }
          else if (d.desc_status === 'failed') { status.textContent = 'Could not describe the photo.'; }
          else { status.textContent = ''; }
          form.dataset.status = d.desc_status;
        }).catch(poll);
      }, 3000);
    })();
  }

  function bulkPage() {
    var waiting = document.getElementById('waiting');
    if (waiting) {
      (function poll() {
        setTimeout(function () {
          fetch('/api/bulk/' + waiting.dataset.job).then(function (r) { return r.json(); }).then(function (d) {
            if (d.status === 'pending') return poll();
            location.reload();
          }).catch(poll);
        }, 3000);
      })();
    }
    var add = document.getElementById('bulk-add-row'), rows = document.getElementById('bulk-rows');
    if (add && rows) {
      add.addEventListener('click', function () {
        var i = rows.children.length;
        var li = document.createElement('li'); li.className = 'bulk-row';
        li.innerHTML = '<input type="checkbox" name="keep" value="' + i + '" checked aria-label="Keep this item">' +
          '<input type="text" name="name" maxlength="120" placeholder="Item name" aria-label="Item name">';
        rows.appendChild(li);
        li.querySelector('input[type=text]').focus();
      });
    }
  }

  function pickAll(formId, allId, noneId) {
    var form = document.getElementById(formId);
    if (!form) return;
    function set(v) { form.querySelectorAll('input[type=checkbox]').forEach(function (c) { c.checked = v; }); }
    document.getElementById(allId).addEventListener('click', function () { set(true); });
    document.getElementById(noneId).addEventListener('click', function () { set(false); });
  }

  return { photoPreview: photoPreview, goneSwitch: goneSwitch, watchDescription: watchDescription, bulkPage: bulkPage, pickAll: pickAll };
})();
