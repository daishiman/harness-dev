/**
 * スライドアニメーション定義
 * 各スライドタイプごとのenter/leaveアニメーションを定義
 */
const animations = {
  // タイトルスライド
  'slide-title': {
    enter: (content) => {
      const tl = gsap.timeline();
      const icon = content.querySelector('.title-icon');
      const title = content.querySelector('.main-title');
      const subtitle = content.querySelector('.sub-title');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(icon,
        { scale: 0, rotation: -180 },
        { scale: 1, rotation: 0, duration: 0.4, ease: 'back.out(1.7)' }
      )
      .fromTo(title,
        { y: 50, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.15'
      )
      .fromTo(subtitle,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power2.out' },
        '-=0.1'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        scale: 1.1,
        opacity: 0,
        duration: 0.2,
        stagger: 0.05,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // メッセージスライド
  'slide-message': {
    enter: (content) => {
      const tl = gsap.timeline();
      const icon = content.querySelector('.message-icon');
      const message = content.querySelector('.main-message');
      const sub = content.querySelector('.sub-message');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(icon,
        { scale: 0 },
        { scale: 1, duration: 0.25, ease: 'back.out(1.7)' }
      )
      .fromTo(message,
        { y: 50, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.1'
      );

      if (sub) {
        tl.fromTo(sub,
          { y: 20, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.2, ease: 'power2.out' },
          '-=0.1'
        );
      }
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        y: -50,
        opacity: 0,
        duration: 0.2,
        stagger: 0.05,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // リストスライド
  'slide-list': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.list-title');
      const items = content.querySelectorAll('.list-item');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(items,
        { x: -30, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.2, stagger: 0.05, ease: 'power2.out' },
        '-=0.1'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const items = content.querySelectorAll('.list-item');
      tl.to(items, {
        x: 30,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // 比較スライド
  'slide-compare': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.compare-title');
      const left = content.querySelector('.compare-item.left');
      const right = content.querySelector('.compare-item.right');
      const vs = content.querySelector('.compare-vs');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(left,
        { x: -100, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.1'
      )
      .fromTo(right,
        { x: 100, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.3'
      )
      .fromTo(vs,
        { scale: 0 },
        { scale: 1, duration: 0.2, ease: 'back.out(1.7)' },
        '-=0.15'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const left = content.querySelector('.compare-item.left');
      const right = content.querySelector('.compare-item.right');
      tl.to(left, { x: -50, opacity: 0, duration: 0.2, ease: 'power2.in' })
        .to(right, { x: 50, opacity: 0, duration: 0.2, ease: 'power2.in' }, '-=0.2');
      return tl;
    }
  },

  // フロースライド
  'slide-flow': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.flow-title');
      const steps = content.querySelectorAll('.flow-step');
      const arrows = content.querySelectorAll('.flow-arrow');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(steps,
        { scale: 0, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.2, stagger: 0.08, ease: 'back.out(1.4)' },
        '-=0.1'
      )
      .fromTo(arrows,
        { opacity: 0, x: -10 },
        { opacity: 1, x: 0, duration: 0.15, stagger: 0.05, ease: 'power2.out' },
        '-=0.25'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const steps = content.querySelectorAll('.flow-step');
      tl.to(steps, {
        scale: 0,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // タイムラインスライド
  'slide-timeline': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.timeline-title');
      const line = content.querySelector('.timeline-line');
      const items = content.querySelectorAll('.timeline-item');

      gsap.set(content, { visibility: 'visible' });
      gsap.set(line, { scaleY: 0, transformOrigin: 'top' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .to(line,
        { scaleY: 1, duration: 0.4, ease: 'power2.out' },
        '-=0.1'
      )
      .fromTo(items,
        { x: -30, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.2, stagger: 0.1, ease: 'power2.out' },
        '-=0.3'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const items = content.querySelectorAll('.timeline-item');
      tl.to(items, {
        y: -30,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // テーブルスライド
  'slide-table': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.table-title');
      const rows = content.querySelectorAll('tr');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(rows,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.15, stagger: 0.04, ease: 'power2.out' },
        '-=0.1'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.querySelector('table'), {
        opacity: 0,
        duration: 0.2,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // アジェンダスライド
  'slide-agenda': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.agenda-title');
      const items = content.querySelectorAll('.agenda-item');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(items,
        { x: -50, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.2, stagger: 0.06, ease: 'power2.out' },
        '-=0.1'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const items = content.querySelectorAll('.agenda-item');
      tl.to(items, {
        x: 50,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // セクションヘッダースライド
  'slide-section': {
    enter: (content) => {
      const tl = gsap.timeline();
      const number = content.querySelector('.section-number');
      const icon = content.querySelector('.section-icon');
      const title = content.querySelector('.section-title');
      const divider = content.querySelector('.section-divider');
      const subtitle = content.querySelector('.section-subtitle');

      gsap.set(content, { visibility: 'visible' });

      if (number) {
        tl.fromTo(number,
          { y: -20, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.2, ease: 'power2.out' }
        );
      }
      if (icon) {
        tl.fromTo(icon,
          { scale: 0, rotation: -90 },
          { scale: 1, rotation: 0, duration: 0.3, ease: 'back.out(1.7)' },
          '-=0.1'
        );
      }
      tl.fromTo(title,
        { y: 50, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.15'
      );
      if (divider) {
        tl.fromTo(divider,
          { scaleX: 0 },
          { scaleX: 1, duration: 0.25, ease: 'power2.out' },
          '-=0.15'
        );
      }
      if (subtitle) {
        tl.fromTo(subtitle,
          { y: 20, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.2, ease: 'power2.out' },
          '-=0.1'
        );
      }
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        scale: 0.95,
        opacity: 0,
        duration: 0.2,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // 統計スライド
  'slide-stats': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.stats-title');
      const items = content.querySelectorAll('.stat-item');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      )
      .fromTo(items,
        { scale: 0.5, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.3, stagger: 0.08, ease: 'back.out(1.4)' },
        '-=0.1'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const items = content.querySelectorAll('.stat-item');
      tl.to(items, {
        scale: 0.8,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // 引用スライド
  'slide-quote': {
    enter: (content) => {
      const tl = gsap.timeline();
      const mark = content.querySelector('.quote-mark');
      const text = content.querySelector('.quote-text');
      const author = content.querySelector('.quote-author');
      const source = content.querySelector('.quote-source');

      gsap.set(content, { visibility: 'visible' });

      if (mark) {
        tl.fromTo(mark,
          { scale: 0, opacity: 0 },
          { scale: 1, opacity: 0.3, duration: 0.3, ease: 'back.out(1.7)' }
        );
      }
      tl.fromTo(text,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.1'
      );
      if (author) {
        tl.fromTo(author,
          { y: 20, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.2, ease: 'power2.out' },
          '-=0.1'
        );
      }
      if (source) {
        tl.fromTo(source,
          { opacity: 0 },
          { opacity: 1, duration: 0.15, ease: 'power2.out' },
          '-=0.05'
        );
      }
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        y: -30,
        opacity: 0,
        duration: 0.2,
        stagger: 0.04,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // 画像スライド
  'slide-image': {
    enter: (content) => {
      const tl = gsap.timeline();
      const imgContainer = content.querySelector('.image-container');
      const imgContent = content.querySelector('.image-content');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(imgContainer,
        { x: -50, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.3, ease: 'power3.out' }
      )
      .fromTo(imgContent?.children || [],
        { x: 30, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.25, stagger: 0.05, ease: 'power2.out' },
        '-=0.15'
      );
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        opacity: 0,
        duration: 0.2,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // 図解スライド
  'slide-diagram': {
    enter: (content) => {
      const tl = gsap.timeline();
      const title = content.querySelector('.diagram-title');
      const center = content.querySelector('.diagram-center');
      const nodes = content.querySelectorAll('.diagram-node');
      const pyramidLevels = content.querySelectorAll('.pyramid-level');

      gsap.set(content, { visibility: 'visible' });

      tl.fromTo(title,
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, ease: 'power3.out' }
      );

      if (center) {
        tl.fromTo(center,
          { scale: 0 },
          { scale: 1, duration: 0.3, ease: 'back.out(1.7)' },
          '-=0.1'
        );
      }

      if (nodes.length > 0) {
        tl.fromTo(nodes,
          { scale: 0, opacity: 0 },
          { scale: 1, opacity: 1, duration: 0.2, stagger: 0.05, ease: 'back.out(1.4)' },
          '-=0.15'
        );
      }

      if (pyramidLevels.length > 0) {
        tl.fromTo(pyramidLevels,
          { scaleX: 0, opacity: 0 },
          { scaleX: 1, opacity: 1, duration: 0.2, stagger: 0.06, ease: 'power2.out' },
          '-=0.1'
        );
      }

      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      const nodes = content.querySelectorAll('.diagram-node, .pyramid-level');
      tl.to(nodes, {
        scale: 0,
        opacity: 0,
        duration: 0.15,
        stagger: 0.03,
        ease: 'power2.in'
      });
      return tl;
    }
  },

  // ヒーロースライド
  'slide-hero': {
    enter: (content) => {
      const tl = gsap.timeline();
      const icon = content.querySelector('.hero-icon');
      const title = content.querySelector('.hero-title');
      const subtitle = content.querySelector('.hero-subtitle');
      const badge = content.querySelector('.hero-badge');

      gsap.set(content, { visibility: 'visible' });

      if (icon) {
        tl.fromTo(icon,
          { scale: 0, rotation: -90 },
          { scale: 1, rotation: 0, duration: 0.4, ease: 'back.out(1.7)' }
        );
      }
      tl.fromTo(title,
        { y: 50, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3, ease: 'power3.out' },
        '-=0.2'
      );
      if (subtitle) {
        tl.fromTo(subtitle,
          { y: 30, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.25, ease: 'power2.out' },
          '-=0.15'
        );
      }
      if (badge) {
        tl.fromTo(badge,
          { scale: 0 },
          { scale: 1, duration: 0.2, ease: 'back.out(1.7)' },
          '-=0.1'
        );
      }
      return tl;
    },
    leave: (content) => {
      const tl = gsap.timeline();
      tl.to(content.children, {
        scale: 0.95,
        opacity: 0,
        duration: 0.2,
        stagger: 0.04,
        ease: 'power2.in'
      });
      return tl;
    }
  }
};
