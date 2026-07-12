<section class="slider__item slide-process" data-section="{{section}}" data-slide-type="process" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="process-container">
      {{#steps}}
      <div class="process-item">
        <div class="process-num">{{num}}</div>
        <div class="process-body">
          <div class="process-title">{{label}}</div>
          {{#desc}}<div class="process-desc text-note">{{desc}}</div>{{/desc}}
        </div>
      </div>
      {{/steps}}
    </div>
  </div>
</section>
