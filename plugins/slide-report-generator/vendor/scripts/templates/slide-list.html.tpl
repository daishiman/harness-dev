<section class="slider__item slide-slide-list" data-section="{{section}}" data-slide-type="slide-list" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <ul class="list">
      {{#items}}
      <li class="list-item">
        {{#icon}}<i class="{{icon}}" aria-hidden="true"></i>{{/icon}}
        <span class="list-label">{{label}}</span>
        {{#desc}}<span class="list-desc text-note">{{desc}}</span>{{/desc}}
      </li>
      {{/items}}
    </ul>
  </div>
</section>
