<section class="slider__item slide-icon-grid" data-section="{{section}}" data-slide-type="icon-grid" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="ig-container" style="--ig-cols: {{cols}};">
      {{#items}}
      <div class="ig-item">
        <div class="ig-icon"><i class="{{icon}}" aria-hidden="true"></i></div>
        <div class="ig-label">{{label}}</div>
        {{#desc}}<div class="ig-desc text-note">{{desc}}</div>{{/desc}}
      </div>
      {{/items}}
    </div>
  </div>
</section>
