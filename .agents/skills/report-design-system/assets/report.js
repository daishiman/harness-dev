/* レポート用ランタイム — build-report.mjs が body 末尾へ埋め込む。手で貼らない。
   JSが無くても目次のリンク遷移・本文・印刷は動く (ここは現在地表示とツールチップの上乗せだけ)。 */
(function () {
  "use strict";

  /* ---- 印刷: ボタンから印刷ダイアログを開き、印刷中は開閉 (根拠・図の読み方・用語集) を全部開く ---- */
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-print]")) window.print();
  });
  var reopened = [];
  window.addEventListener("beforeprint", function () {
    reopened = Array.prototype.filter.call(document.querySelectorAll("details:not([open])"), function (d) {
      d.open = true;
      return true;
    });
  });
  window.addEventListener("afterprint", function () {
    reopened.forEach(function (d) { d.open = false; });
    reopened = [];
  });

  /* ---- 用語は共通 TermUI、図の値だけ #tip でマウスに追従する ---- */
  window.TermUI.init();
  var tip = document.getElementById("tip");
  if (tip) {
    document.addEventListener("mouseover", function (e) {
      var termPop = document.getElementById("term-pop");
      var t = e.target.closest("[data-tip]");
      if (!t || (termPop && !termPop.hidden)) { tip.style.opacity = 0; return; }
      tip.textContent = t.getAttribute("data-tip");
      tip.style.opacity = 1;
    });
    document.addEventListener("mousemove", function (e) {
      if (tip.style.opacity != "1") return;
      var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = x + "px";
      tip.style.top = (e.clientY + 16) + "px";
    });
    document.addEventListener("focusin", function (e) {
      if (e.target.closest("a.term")) tip.style.opacity = 0;
    });
  }

  /* ---- 目次: 現在地の追従と、狭い画面での開閉 ---- */
  var toc = document.querySelector("nav.toc");
  if (!toc) return;
  var details = toc.querySelector("details");
  var current = toc.querySelector(".toc-current");
  var links = Array.prototype.slice.call(toc.querySelectorAll("a[href^='#']"));
  var narrow = window.matchMedia("(max-width: 1023px)");

  // 狭い画面では閉じた状態で始める (HTML上は open。JSが無い環境でも目次が読めるように)
  function syncOpen() { if (details) details.open = !narrow.matches; }
  syncOpen();
  if (narrow.addEventListener) narrow.addEventListener("change", syncOpen);

  links.forEach(function (a) {
    a.addEventListener("click", function () { if (narrow.matches && details) details.open = false; });
  });

  var targets = links
    .map(function (a) { return document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1))); })
    .filter(Boolean);
  if (!targets.length) return;

  function setCurrent(id) {
    var active = null;
    links.forEach(function (a) {
      var on = a.getAttribute("href") === "#" + id;
      if (on) { a.setAttribute("aria-current", "location"); active = a; }
      else a.removeAttribute("aria-current");
    });
    if (!active) return;
    if (current) current.textContent = active.getAttribute("data-label") || active.textContent;
    // サイドバー内だけをスクロールさせ、ページ本体は動かさない
    var list = toc.querySelector("details > ol") || toc;
    if (list.scrollHeight > list.clientHeight) {
      var top = active.offsetTop - list.offsetTop;
      if (top < list.scrollTop || top > list.scrollTop + list.clientHeight - active.offsetHeight) {
        list.scrollTop = top - list.clientHeight / 3;
      }
    }
  }

  // 画面上端から 30% の線を越えた最後の見出しを「現在地」とする
  function update() {
    var line = window.innerHeight * 0.3;
    var id = targets[0].id;
    for (var i = 0; i < targets.length; i++) {
      if (targets[i].getBoundingClientRect().top - line <= 0) id = targets[i].id; else break;
    }
    // 最下部まで来たら最後の項目を現在地にする (短い最終セクション対策)
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) id = targets[targets.length - 1].id;
    setCurrent(id);
  }
  var queued = false;
  window.addEventListener("scroll", function () {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(function () { queued = false; update(); });
  }, { passive: true });
  window.addEventListener("resize", update);
  window.addEventListener("hashchange", update);
  update();
})();
