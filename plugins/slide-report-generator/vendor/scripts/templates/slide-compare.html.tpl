<section class="slider__item slide-slide-compare" data-section="{{section}}" data-slide-type="slide-compare" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    {{#axis}}<p class="text-note compare-axis">{{axis}}</p>{{/axis}}
    <div class="compare-container">
      <div class="compare-panel compare-panel--before">
        <h3>{{left.title}}</h3>
        <ul>{{#left.items}}<li>{{.}}</li>{{/left.items}}</ul>
      </div>
      <div class="compare-panel compare-panel--after">
        <h3>{{right.title}}</h3>
        <ul>{{#right.items}}<li>{{.}}</li>{{/right.items}}</ul>
      </div>
    </div>
  </div>
</section>
