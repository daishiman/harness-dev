<section class="slider__item slide-slide-code-compare" data-section="{{section}}" data-slide-type="slide-code-compare" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="code-compare">
      <div class="code-panel code-panel--before">
        <div class="code-panel__header">{{before.label}}</div>
        <pre><code class="lang-{{before.lang}}">{{before.code}}</code></pre>
      </div>
      <div class="code-panel code-panel--after">
        <div class="code-panel__header">{{after.label}}</div>
        <pre><code class="lang-{{after.lang}}">{{after.code}}</code></pre>
      </div>
    </div>
  </div>
</section>
