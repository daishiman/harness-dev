/* slide-skeleton.js — 生成物。手で編集しない。
 * 正本: assets/slide-templates/frame-contract.json
 * 再生成: python3 scripts/build-slide-skeleton-js.py
 * 検証:   python3 scripts/build-slide-skeleton-js.py --check
 *
 * ひな形が宣言する 2 つの契約を履行する:
 *   data-autofit  溢れている間だけ font-size を下げる (下限 18px)
 *   --srg-fit     面 1280x720 を親要素へ収める倍率
 * 外部依存なし。成果物へは scripts.js の末尾へ連結して届ける
 * (インライン <script> にはしない。assets/slide-templates/README.md「成果物への届け方」)。
 */
(function () {
  'use strict';

  var CANVAS_W = 1280;
  var CANVAS_H = 720;
  var FS_MIN = 18;
  var STEP = 1;          // 1px ずつ下げる。粗くすると下限手前で無駄に小さくなる
  var MAX_STEPS = 200;   // 測定が病的な場合の保険 (無限ループにしない)

  function slides(root) {
    return Array.prototype.slice.call((root || document).querySelectorAll('.srg-slide'));
  }

  /* 面を親要素へ収める倍率を --srg-fit へ書く。
     面の内部は常に 1280x720 の絶対座標のままなので、
     画面と PDF は「スケール係数が違うだけの同一物」であり続ける。 */
  function fitStage(root) {
    slides(root).forEach(function (slide) {
      var box = slide.parentElement;
      if (!box) return;
      var w = box.clientWidth;
      var h = box.clientHeight;
      if (!w || !h) return;
      var fit = Math.min(w / CANVAS_W, h / CANVAS_H);
      slide.style.setProperty('--srg-fit', String(Math.round(fit * 10000) / 10000));
    });
  }

  /* 溢れている間だけ font-size を下げる。下限で止まり、止まったことを表に出す。 */
  function autofitOne(el) {
    el.style.removeProperty('font-size');           // 冪等にするため毎回初期値へ戻す
    el.removeAttribute('data-autofit-floored');
    var size = parseFloat(getComputedStyle(el).fontSize);
    if (!size) return false;

    var steps = 0;
    while (el.scrollHeight > el.clientHeight + 0.5 && size > FS_MIN && steps < MAX_STEPS) {
      size -= STEP;
      el.style.fontSize = size + 'px';
      steps++;
    }

    var stillOverflowing = el.scrollHeight > el.clientHeight + 0.5;
    if (size <= FS_MIN && stillOverflowing) {
      /* 下限に達してなお溢れている。ここから先は縮めない —
         読めない文字で「収まった」ことにするのは、溢れているのと同じ。
         面を割るか本文を削るべき面として印を付ける。 */
      el.style.fontSize = FS_MIN + 'px';
      el.setAttribute('data-autofit-floored', 'true');
      return true;
    }
    return false;
  }

  function autofit(root) {
    slides(root).forEach(function (slide) {
      var floored = false;
      Array.prototype.forEach.call(slide.querySelectorAll('[data-autofit]'), function (el) {
        if (autofitOne(el)) floored = true;
      });
      if (floored) slide.setAttribute('data-overflow', 'true');
      else slide.removeAttribute('data-overflow');
    });
  }

  function apply(root) {
    autofit(root);   // 先に文字を決めてから
    fitStage(root);  // 面の倍率を測る (順序が逆だと 1 フレーム分ズレる)
  }

  /* 起動と再実行。フォントの読み込み完了で行数が変わるので、そこでも測り直す。 */
  function boot() {
    apply(document);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { apply(document); });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  var pending = null;
  window.addEventListener('resize', function () {
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(function () { pending = null; apply(document); });
  });

  /* 印刷の直前に --srg-fit を等倍へ戻し、文字だけ測り直す。
     **二重掛けを止めているのはこの JS ではなく print CSS の方**である
     (`@media print` が transform: none と margin: 0 を宣言するので、
     --srg-fit が残っていても zoom と重ならない)。headless の page.pdf() は
     beforeprint を発火しないことがあり、ここを唯一の防波堤にはできない。
     この handler が担うのは、印刷プレビューを出したブラウザで
     倍率の変わった面に対して autofit を測り直すことだけ。 */
  window.addEventListener('beforeprint', function () {
    slides(document).forEach(function (s) { s.style.setProperty('--srg-fit', '1'); });
    autofit(document);
  });
  window.addEventListener('afterprint', function () { apply(document); });

  window.SRGSkeleton = { apply: apply, autofit: autofit, fitStage: fitStage };
})();
