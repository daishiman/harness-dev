<section class="slider__item slide-grid" data-section="{{section}}" data-slide-type="grid" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="grid-container" style="--grid-cols: {{cols}};">
      {{#cells}}<div class="grid-cell">{{.}}</div>{{/cells}}
    </div>
  </div>
</section>
