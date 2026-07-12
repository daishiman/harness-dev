<section class="slider__item slide-compare" data-section="{{section}}" data-slide-type="compare" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="compare-container">
      <div class="compare-panel compare-panel--before">
        <h3>{{before.title}}</h3>
        <ul>{{#before.items}}<li>{{.}}</li>{{/before.items}}</ul>
      </div>
      <div class="compare-panel compare-panel--after">
        <h3>{{after.title}}</h3>
        <ul>{{#after.items}}<li>{{.}}</li>{{/after.items}}</ul>
      </div>
    </div>
  </div>
</section>
