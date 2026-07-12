<section class="slider__item slide-slide-icon-grid" data-section="{{section}}" data-slide-type="slide-icon-grid" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="ig-container" style="--ig-cols: {{columns}};">
      {{#items}}
      <div class="ig-item{{#selected}} is-selected{{/selected}}">
        <div class="ig-icon"><i class="{{icon}}" aria-hidden="true"></i></div>
        <div class="ig-label">{{label}}</div>
      </div>
      {{/items}}
    </div>
  </div>
</section>
