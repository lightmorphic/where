/* QR scanning with the phone camera. Uses the browser's own detector when it
   has one, and the bundled jsQR otherwise. */
(function () {
  'use strict';
  var video = document.getElementById('video'), canvas = document.getElementById('canvas');
  var status = document.getElementById('scan-status'), startBtn = document.getElementById('scan-start');
  var ctx = canvas.getContext('2d', { willReadFrequently: true });
  var stream = null, done = false, detector = null;

  if ('BarcodeDetector' in window) {
    try { detector = new BarcodeDetector({ formats: ['qr_code'] }); } catch (e) { detector = null; }
  }

  function found(text) {
    if (done) return;
    done = true;
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    var m = /\/places\/(\d+)/.exec(text);
    if (m) { status.textContent = 'Opening…'; location.href = '/places/' + m[1]; return; }
    status.textContent = 'That is not a Where label: ' + text;
    startBtn.hidden = false; startBtn.textContent = 'Scan again';
    done = false;
  }

  function tick() {
    if (done || !stream) return;
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      if (detector) {
        detector.detect(video).then(function (codes) {
          if (codes.length) found(codes[0].rawValue); else requestAnimationFrame(tick);
        }).catch(function () { detector = null; requestAnimationFrame(tick); });
        return;
      }
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
      var code = window.jsQR ? jsQR(img.data, img.width, img.height, { inversionAttempts: 'dontInvert' }) : null;
      if (code && code.data) { found(code.data); return; }
    }
    requestAnimationFrame(tick);
  }

  function start() {
    done = false; startBtn.hidden = true;
    status.textContent = 'Starting camera…';
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = 'This browser cannot open the camera. Open the app over https and try again.';
      return;
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
      .then(function (s) {
        stream = s; video.srcObject = s;
        return video.play();
      })
      .then(function () { status.textContent = 'Point at a label'; requestAnimationFrame(tick); })
      .catch(function (err) {
        status.textContent = 'Camera not available: ' + (err && err.message ? err.message : err);
        startBtn.hidden = false;
      });
  }

  startBtn.addEventListener('click', start);
  document.addEventListener('visibilitychange', function () {
    if (document.hidden && stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; startBtn.hidden = false; status.textContent = 'Camera paused'; }
  });
  start();
})();
