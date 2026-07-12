<section class="slider__item slide-slide-timeline" data-section="{{section}}" data-slide-type="slide-timeline" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <ol class="timeline">
      {{#events}}
      <li class="timeline-item">
        <div class="timeline-date">{{date}}</div>
        <div class="timeline-title">{{label}}</div>
        {{#desc}}<div class="timeline-desc text-note">{{desc}}</div>{{/desc}}
      </li>
      {{/events}}
    </ol>
  </div>
</section>
