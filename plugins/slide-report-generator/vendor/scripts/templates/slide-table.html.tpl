<section class="slider__item slide-slide-table" data-section="{{section}}" data-slide-type="slide-table" data-index="{{index}}">
  <div class="slider__content">
    <h2>{{title}}</h2>
    <table class="table">
      <thead><tr>{{#headers}}<th>{{.}}</th>{{/headers}}</tr></thead>
      <tbody>
        {{#rows}}<tr>{{#cells}}<td>{{.}}</td>{{/cells}}</tr>{{/rows}}
      </tbody>
    </table>
  </div>
</section>
