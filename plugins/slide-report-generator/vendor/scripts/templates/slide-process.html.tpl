<section class="slider__item slide-slide-process" data-section="{{section}}" data-slide-type="slide-process" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <div class="process-container">
      {{#steps}}
      <div class="process-item">
        <div class="process-num">{{number}}</div>
        <div class="process-body">
          <div class="process-title">{{label}}</div>
          <div class="process-desc text-note">{{desc}}</div>
        </div>
      </div>
      {{/steps}}
    </div>
  </div>
</section>
