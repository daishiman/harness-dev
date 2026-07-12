<section class="slider__item slide-list" data-section="{{section}}" data-slide-type="list" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <ul class="list">
      {{#items}}
      <li class="list-item">{{.}}</li>
      {{/items}}
    </ul>
    {{#note}}<p class="text-note">{{note}}</p>{{/note}}
  </div>
</section>
