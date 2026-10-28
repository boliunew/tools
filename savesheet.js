/* 保存图片的面板：手机上处理完先把图给你看，再点「存到相册」。
   为什么要多点一下：处理大图要几秒钟，浏览器会认为那已经不是你刚点的操作，
   直接弹系统分享菜单会被悄悄拦下来。新的一次点击就没这个问题。
   电脑上直接下载，弹一个小提示。
   用法：SaveSheet.show(blob, '文件名.jpg', { w: 宽, h: 高 }) */
(function () {
  'use strict';
  var css = '' +
    '.ss-ov{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.62);display:flex;align-items:flex-end;justify-content:center}' +
    '@media (min-width:700px){.ss-ov{align-items:center}}' +
    '.ss-pn{width:100%;max-width:520px;max-height:92dvh;overflow:auto;background:#FFFDF8;color:#1D2028;border-radius:18px 18px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom));font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}' +
    '@media (min-width:700px){.ss-pn{border-radius:18px}}' +
    '@media (prefers-color-scheme:dark){.ss-pn{background:#1B1F27;color:#E9ECF1}.ss-b{background:#252A35!important;border-color:#2B303B!important}}' +
    '.ss-pn h3{margin:0 0 10px;font-size:17px}' +
    '.ss-im{display:block;width:100%;max-height:48dvh;object-fit:contain;border-radius:10px;background:#000;-webkit-touch-callout:default}' +
    '.ss-meta{font-size:12.5px;opacity:.65;margin:6px 0 12px}' +
    '.ss-b{display:block;width:100%;border:1px solid #E3DED3;background:#EEE9DF;color:inherit;border-radius:12px;padding:12px;font:inherit;font-weight:600;margin-top:8px;cursor:pointer;text-align:center;text-decoration:none}' +
    '.ss-b.pri{background:#2C6E8F!important;border-color:#2C6E8F!important;color:#fff}' +
    '.ss-hint{font-size:12.5px;opacity:.7;margin-top:10px}' +
    '.ss-msg{font-size:13px;color:#C0392B;margin-top:8px;display:none}' +
    '.ss-toast{position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:9999;background:rgba(20,22,28,.92);color:#fff;padding:9px 16px;border-radius:999px;font:14px -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;max-width:90vw}';
  var styled = false;
  function addCss() { if (styled) return; styled = true; var s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }
  function mb(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB'; }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function isPhone() {
    try { if (window.matchMedia('(pointer:coarse)').matches) return true; } catch (e) { }
    return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
  }
  function download(url, name) {
    var a = document.createElement('a'); a.href = url; a.download = name; a.rel = 'noopener';
    document.body.appendChild(a); a.click(); setTimeout(function () { a.remove(); }, 0);
  }
  function toast(t) {
    addCss(); var d = document.createElement('div'); d.className = 'ss-toast'; d.textContent = t;
    document.body.appendChild(d); setTimeout(function () { d.remove(); }, 2600);
  }

  function show(blob, name, info) {
    addCss();
    var url = URL.createObjectURL(blob);
    if (!isPhone()) {
      download(url, name); toast('已下载：' + name);
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      return;
    }
    var file = null; try { file = new File([blob], name, { type: blob.type || 'image/jpeg' }); } catch (e) { }
    var canShare = !!(file && navigator.canShare && navigator.canShare({ files: [file] }));
    var ov = document.createElement('div'); ov.className = 'ss-ov';
    ov.innerHTML = '<div class="ss-pn" role="dialog" aria-label="保存图片">' +
      '<h3>图片做好了</h3>' +
      '<img class="ss-im" alt="处理好的图片">' +
      '<div class="ss-meta">' + esc(name) + (info && info.w ? ' · ' + info.w + '×' + info.h : '') + ' · ' + mb(blob.size) + '</div>' +
      (canShare ? '<button class="ss-b pri" data-a="share">存到相册 / 分享</button>' : '') +
      '<button class="ss-b' + (canShare ? '' : ' pri') + '" data-a="dl">⬇️ 下载到「文件」</button>' +
      '<div class="ss-msg"></div>' +
      '<div class="ss-hint">也可以<b>长按上面的图片</b>，选「存储到照片」或「下载图片」。</div>' +
      '<button class="ss-b" data-a="close">关闭</button></div>';
    ov.querySelector('.ss-im').src = url;
    function close() { ov.remove(); setTimeout(function () { URL.revokeObjectURL(url); }, 1000); }
    function msg(t) { var m = ov.querySelector('.ss-msg'); m.textContent = t; m.style.display = 'block'; }
    ov.addEventListener('click', function (e) {
      if (e.target === ov) return close();
      var b = e.target.closest('[data-a]'); if (!b) return;
      var a = b.getAttribute('data-a');
      if (a === 'close') close();
      else if (a === 'dl') download(url, name);
      else if (a === 'share') {
        navigator.share({ files: [file], title: name }).then(close).catch(function (err) {
          if (err && err.name === 'AbortError') return;          // 自己取消了，不用提示
          msg('分享菜单没打开，试试「下载」，或长按图片保存。');
        });
      }
    });
    document.body.appendChild(ov);
  }
  window.SaveSheet = { show: show };
})();
