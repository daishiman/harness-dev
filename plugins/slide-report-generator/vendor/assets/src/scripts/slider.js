/**
 * TweenSliderクラス（16:9対応）
 * GSAPを使用したスライドナビゲーションとアニメーション制御
 */
class TweenSlider {
  constructor(selector) {
    this.slider = document.querySelector(selector);
    this.slideArea = document.querySelector(selector + ' .slide-area');
    this.container = document.querySelector(selector + ' .slider__container');
    this.items = document.querySelectorAll(selector + ' .slider__item');
    this.index = 0;
    this.isAnimating = false;
    // 16:9エリアの幅を使用（ビューポートではなく）
    this.slideWidth = this.slideArea ? this.slideArea.offsetWidth : window.innerWidth;

    this.init();
  }

  init() {
    this.buildNavigation();
    this.bindEvents();
    this.makeActive(0);
    this.playEnterAnimation(0);
    this.updateProgress();
  }

  buildNavigation() {
    const nav = document.getElementById('navigation');
    this.items.forEach((_, i) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = '#' + i;
      a.dataset.index = i;
      // 5個ごと・10個ごとにマーカークラスを追加（1始まりで計算）
      const slideNum = i + 1;
      if (slideNum % 10 === 0) {
        a.classList.add('nav-mark-10');
      } else if (slideNum % 5 === 0) {
        a.classList.add('nav-mark-5');
      }
      a.addEventListener('click', (e) => {
        e.preventDefault();
        this.move(i);
      });
      li.appendChild(a);
      nav.appendChild(li);
    });
  }

  bindEvents() {
    document.getElementById('next').addEventListener('click', () => this.moveToNext());
    document.getElementById('prev').addEventListener('click', () => this.moveToPrev());

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        this.moveToNext();
      }
      if (e.key === 'ArrowLeft') this.moveToPrev();
    });

    window.addEventListener('resize', () => {
      // 16:9エリアの幅を再計算
      this.slideWidth = this.slideArea ? this.slideArea.offsetWidth : window.innerWidth;
      gsap.set(this.container, { x: -this.index * this.slideWidth });
    });

    // スワイプ対応
    this.bindSwipeEvents();
  }

  bindSwipeEvents() {
    let touchStartX = 0;
    let touchStartY = 0;
    const minSwipeDistance = 50;
    const target = this.slideArea || this.slider;

    target.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    target.addEventListener('touchend', (e) => {
      const touchEndX = e.changedTouches[0].screenX;
      const touchEndY = e.changedTouches[0].screenY;
      const diffX = touchStartX - touchEndX;
      const diffY = Math.abs(touchStartY - touchEndY);

      // 横方向のスワイプのみ反応（縦スクロールを妨げない）
      if (Math.abs(diffX) > minSwipeDistance && Math.abs(diffX) > diffY) {
        if (diffX > 0) {
          this.moveToNext();
        } else {
          this.moveToPrev();
        }
      }
    }, { passive: true });
  }

  makeActive(index) {
    const navItems = document.querySelectorAll('.slider-navigation a');
    this.items.forEach((item, i) => {
      item.classList.toggle('is-active', i === index);
      navItems[i]?.classList.toggle('is-active', i === index);
    });
  }

  getSlideType(slide) {
    const classes = slide.className.split(' ');
    for (const cls of classes) {
      if (cls.startsWith('slide-') && cls !== 'slider__item') {
        return cls;
      }
    }
    return 'slide-message';
  }

  playEnterAnimation(index) {
    const slide = this.items[index];
    const content = slide.querySelector('.slider__content');
    const type = this.getSlideType(slide);

    if (animations[type] && animations[type].enter) {
      return animations[type].enter(content);
    } else {
      gsap.set(content, { visibility: 'visible' });
      return gsap.timeline();
    }
  }

  playLeaveAnimation(index) {
    const slide = this.items[index];
    const content = slide.querySelector('.slider__content');
    const type = this.getSlideType(slide);

    if (animations[type] && animations[type].leave) {
      return animations[type].leave(content);
    } else {
      return gsap.timeline();
    }
  }

  async move(index) {
    if (this.isAnimating || index === this.index || index < 0 || index >= this.items.length) {
      return;
    }

    this.isAnimating = true;

    const masterTl = gsap.timeline({
      onComplete: () => {
        this.isAnimating = false;
      }
    });

    // Leave animation
    masterTl.add(this.playLeaveAnimation(this.index));

    // Slide movement
    masterTl.to(this.container, {
      x: -index * this.slideWidth,
      duration: 0.25,
      ease: 'power3.inOut'
    }, '-=0.1');

    // Enter animation
    masterTl.add(this.playEnterAnimation(index), '-=0.15');

    this.index = index;
    this.makeActive(index);
    this.updateProgress();
  }

  moveToNext() {
    // ループ: 最後のスライド → 最初へ
    const nextIndex = (this.index + 1) % this.items.length;
    this.move(nextIndex);
  }

  moveToPrev() {
    // ループ: 最初のスライド → 最後へ
    const prevIndex = (this.index - 1 + this.items.length) % this.items.length;
    this.move(prevIndex);
  }

  updateProgress() {
    const progress = ((this.index + 1) / this.items.length) * 100;
    document.getElementById('progress').style.width = progress + '%';
    document.getElementById('slideNumber').textContent = (this.index + 1) + ' / ' + this.items.length;
  }
}
