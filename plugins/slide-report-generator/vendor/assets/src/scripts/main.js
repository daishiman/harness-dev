/**
 * AutoLineBreaker: 自動改行・カードサイズ動的調整
 * オプション機能: デフォルトOFF（LLMによる意図的改行を優先）
 */
class AutoLineBreaker {
  constructor(options = {}) {
    this.maxChars = options.maxChars || 35;
    this.minChars = options.minChars || 15;

    // 改行候補の優先度（高い順）
    this.breakPriorities = [
      { pattern: /([。！？])(?!<br>)/g, priority: 100 },  // 句点の後
      { pattern: /([、])(?!<br>)/g, priority: 80 },       // 読点の後
      { pattern: /(ます|です|した|ない)(?!<br>)/g, priority: 70 }, // 文末表現
      { pattern: /(は|が|を|に|で|と|も|の)(?!<br>)/g, priority: 50 }, // 助詞の後
      { pattern: /(、|・)(?!<br>)/g, priority: 40 },      // 中黒の後
    ];

    // 対象セレクタ
    this.targetSelectors = [
      '.list-item span',
      '.flow-step span',
      '.compare-item li',
      '.grid-card p',
      '.point-card p',
      '.feature-card p',
      '.timeline-content p',
      '.persona-card p',
      '.step-desc',
      '.card-desc'
    ];
  }

  init() {
    this.processAllElements();
    this.adjustCardHeights();
  }

  processAllElements() {
    const selector = this.targetSelectors.join(', ');
    const elements = document.querySelectorAll(selector);

    elements.forEach(el => {
      // 既に<br>が含まれている場合はスキップ
      if (el.innerHTML.includes('<br>')) return;

      const text = el.textContent.trim();
      if (text.length > this.minChars) {
        el.innerHTML = this.insertLineBreaks(text);
      }
    });
  }

  insertLineBreaks(text) {
    // 短いテキストは改行不要
    if (text.length <= this.maxChars) {
      return text;
    }

    const breaks = [];
    let lastBreakPos = 0;

    while (lastBreakPos < text.length) {
      const segment = text.slice(lastBreakPos, lastBreakPos + this.maxChars + 10);
      let bestBreakPos = -1;
      let bestPriority = 0;

      // 各パターンで改行候補を探す
      for (const rule of this.breakPriorities) {
        const matches = [...segment.matchAll(rule.pattern)];
        for (const m of matches) {
          const pos = lastBreakPos + m.index + m[0].length;
          const charsSinceLastBreak = pos - lastBreakPos;

          // 最大文字数の70-110%の範囲で改行
          if (charsSinceLastBreak >= this.maxChars * 0.7 &&
              charsSinceLastBreak <= this.maxChars * 1.3) {
            if (rule.priority > bestPriority) {
              bestPriority = rule.priority;
              bestBreakPos = pos;
            }
          }
        }
      }

      // 候補が見つからない場合、強制的に最大文字数で改行
      if (bestBreakPos === -1) {
        const forcePos = lastBreakPos + this.maxChars;
        if (forcePos < text.length) {
          bestBreakPos = forcePos;
        } else {
          break;
        }
      }

      if (bestBreakPos > lastBreakPos) {
        breaks.push(bestBreakPos);
        lastBreakPos = bestBreakPos;
      } else {
        break;
      }

      // 無限ループ防止
      if (breaks.length > 10) break;
    }

    // 改行を挿入（後ろから挿入して位置ズレを防ぐ）
    let result = text;
    for (let i = breaks.length - 1; i >= 0; i--) {
      const pos = breaks[i];
      if (pos < result.length) {
        result = result.slice(0, pos) + '<br>' + result.slice(pos);
      }
    }

    return result;
  }

  adjustCardHeights() {
    // カードグループを検出して高さを揃える
    const cardGroups = [
      '.slide-list .list-item',
      '.slide-flow .flow-step',
      '.slide-compare .compare-item',
      '.point-cards .point-card',
      '.grid-container .grid-card'
    ];

    cardGroups.forEach(selector => {
      const cards = document.querySelectorAll(selector);
      if (cards.length === 0) return;

      // 各スライド内で高さを揃える
      const slides = document.querySelectorAll('.slider__item');
      slides.forEach(slide => {
        const slideCards = slide.querySelectorAll(selector.split(' ').pop());
        if (slideCards.length === 0) return;

        // 最大高さを計算
        let maxHeight = 0;
        slideCards.forEach(card => {
          card.style.height = 'auto';
          const height = card.offsetHeight;
          if (height > maxHeight) maxHeight = height;
        });

        // 全カードに最大高さを適用（min-heightで統一）
        slideCards.forEach(card => {
          card.style.minHeight = maxHeight + 'px';
        });
      });
    });
  }
}

// =================================================================
// 初期化
// =================================================================
document.addEventListener('DOMContentLoaded', () => {
  // AutoLineBreaker: デフォルトOFF（LLMによる意図的改行を優先）
  // 機械的改行が必要な場合のみ有効化:
  // new AutoLineBreaker({ maxChars: 35, minChars: 15 }).init();

  // スライダー初期化
  new TweenSlider('#slider');
});
