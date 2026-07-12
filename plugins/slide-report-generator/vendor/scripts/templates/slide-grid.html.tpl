<section class="slider__item slide-slide-grid" data-section="{{section}}" data-slide-type="slide-grid" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="grid-container" style="--grid-cols: 3;">
      {{#cards}}
      <div class="grid-cell">
        {{#icon}}<i class="{{icon}}" aria-hidden="true"></i>{{/icon}}
        <div class="grid-cell-title">{{title}}</div>
        {{#desc}}<div class="grid-cell-desc text-note">{{desc}}</div>{{/desc}}
      </div>
      {{/cards}}
    </div>
  </div>
</section>
