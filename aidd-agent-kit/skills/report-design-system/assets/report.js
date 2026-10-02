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

  /* ---- 浮かせて出す説明。1つの箱 (#tip) を2つの用途で使い分ける ----
     (a) 図の値 (svg の [data-tip]): マウスに追従する1行。
     (b) 用語の説明 (.term): 用語の下に出す2行。ホバー・キーボードのフォーカス・クリック/タップの3経路で開く。
         クリックで固定 (pin) し、Esc・外側のクリック・もう一度クリックで閉じる。
         説明文は末尾の用語集 (dt/dd) だけが持ち、ここはそれを読むだけ (同じ文を2か所に書かない)。
         JS が無い環境では .term は用語集へのリンクとして働く。 */
  var tip = document.getElementById("tip");
  if (tip) {
    var pinned = null;   // クリックで固定中の .term
    var hovered = null;  // ホバー/フォーカスで一時的に出している .term
    var restoringFocus = false; // Esc で閉じた直後にフォーカスを戻している最中

    function hide() {
      tip.style.opacity = 0;
      tip.className = "tooltip";
      hovered = pinned = null;
    }

    /** 用語集の dt (#gl-*) の次の dd から説明を読む。見つからなければ何も出さない */
    function showTerm(a) {
      var dt = document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
      var dd = dt && dt.nextElementSibling;
      if (!dd || dd.tagName !== "DD") return false;
      tip.className = "tooltip tip-rich";
      tip.innerHTML = "";
      var head = document.createElement("b");
      head.textContent = a.getAttribute("data-term") || dt.textContent;
      tip.appendChild(head);
      Array.prototype.forEach.call(dd.children, function (span) {
        var p = document.createElement("span");
        p.textContent = span.textContent;
        tip.appendChild(p);
      });
      tip.style.opacity = 1;
      // 用語の下に出し、画面からはみ出す側は内側へ寄せる (下に入らなければ上へ)
      var r = a.getBoundingClientRect();
      var left = Math.max(8, Math.min(r.left, window.innerWidth - tip.offsetWidth - 8));
      var top = r.bottom + 8;
      if (top + tip.offsetHeight > window.innerHeight - 8) top = Math.max(8, r.top - tip.offsetHeight - 8);
      tip.style.left = left + "px";
      tip.style.top = top + "px";
      return true;
    }

    document.addEventListener("mouseover", function (e) {
      var term = e.target.closest(".term");
      if (term) {
        if (pinned) return;
        if (showTerm(term)) hovered = term;
        return;
      }
      if (pinned) return;
      if (hovered) hide();
      var t = e.target.closest("[data-tip]");
      if (!t) { tip.style.opacity = 0; return; }
      tip.className = "tooltip";
      tip.textContent = t.getAttribute("data-tip");
      tip.style.opacity = 1;
    });
    document.addEventListener("mousemove", function (e) {
      if (tip.style.opacity == "1" && !pinned && !hovered) {
        var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
        tip.style.left = x + "px";
        tip.style.top = (e.clientY + 16) + "px";
      }
    });
    // キーボード: Tab で用語へ移ると出て、離れると消える
    document.addEventListener("focusin", function (e) {
      var term = e.target.closest(".term");
      if (!term || pinned || restoringFocus) return;
      if (showTerm(term)) hovered = term;
    });
    document.addEventListener("focusout", function (e) {
      if (!pinned && hovered && e.target.closest(".term") === hovered) hide();
    });
    // クリック/タップ: 用語集へ飛ばずにその場で固定する (もう一度押すか、外側・Esc で閉じる)
    document.addEventListener("click", function (e) {
      var term = e.target.closest(".term");
      if (term) {
        e.preventDefault();
        var same = pinned === term;
        hide();
        if (!same && showTerm(term)) pinned = term;
        return;
      }
      if (pinned) hide();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !pinned) return;
      var focus = pinned;
      hide();
      // 閉じた直後にフォーカスを戻すと focusin で開き直ってしまうので、この1回だけ止める
      restoringFocus = true;
      focus.focus();
      restoringFocus = false;
    });
    window.addEventListener("scroll", function () { if (pinned || hovered) hide(); }, { passive: true });
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
