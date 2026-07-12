<section class="slider__item slide-d3 d3-isotype" data-section="{{section}}" data-slide-type="d3-isotype" data-index="{{index}}" data-d3-component="isotype">
  <div class="slider__content">
    {{#title}}<h2>{{title}}</h2>{{/title}}
    <div class="d3-mount" id="d3-mount-{{index}}" data-d3-component="isotype"></div>
    <script type="application/json" data-d3-mount data-d3-target="d3-mount-{{index}}" data-d3-component="isotype">{{{configJson}}}</script>
  </div>
</section>
