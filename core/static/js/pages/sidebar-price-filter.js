/**
 * Wires up the sidebar's "Fill by price" widget (templates/shop/sidebar.html):
 * the price slider, the Color checkboxes, the Item Condition checkboxes,
 * and the "Fillter" button - exactly as designed in the original markup,
 * no UI added or removed.
 *
 * Everything in this widget is now backed by real data from
 * GET /api/v1/products/facets/ (api/v1/views/shop.py, ProductViewSet.facets):
 *  - the price slider's min/max bounds are the real min/max price of
 *    published products, replacing the hardcoded 0-2000 default;
 *  - the Color / Item Condition checkbox labels show real counts of
 *    published products ("Red (7)"), replacing the hardcoded demo
 *    numbers ("Red (56)");
 *  - a Color/Condition option with zero matching published products
 *    is hidden entirely rather than shown with a fake count.
 *
 * The "Fillter" button (price + color + condition -> shop:filter) is
 * unchanged from before. The slider and the Color/Item Condition
 * checkboxes are now additionally live on this page: as soon as the
 * shopper settles on a value, that filter is applied straight to this
 * page's own product grid via window.ShopList (static/js/pages/shop-list.js),
 * the same way Show/Sort/Tags already are.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var submitLink = document.getElementById("sidebarPriceFilterSubmit");
  if (!submitLink) return;

  var COLOR_IDS = ["exampleCheckbox1", "exampleCheckbox2", "exampleCheckbox3"];
  var CONDITION_IDS = ["exampleCheckbox11", "exampleCheckbox21", "exampleCheckbox31"];

  function checkedValues(ids) {
    return ids
      .map(function (id) {
        return document.getElementById(id);
      })
      .filter(function (el) {
        return el && el.checked;
      })
      .map(function (el) {
        return el.value;
      });
  }

  function sliderPrice(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    // The slider formats values as "$500" (see main.js's wNumb config);
    // keep only the digits.
    var digits = el.textContent.replace(/[^0-9.]/g, "");
    return digits === "" ? null : digits;
  }

  // Applies real facet data (from GET products/facets/) to one set of
  // checkboxes: updates each option's "Label (count)" text and hides
  // any option that has no matching published products at all - no
  // fake/zero counts left on screen, and no option invented beyond
  // what's actually in the database.
  function applyFacetOptions(ids, facetList) {
    var byValue = {};
    (facetList || []).forEach(function (opt) {
      byValue[opt.value] = opt;
    });
    ids.forEach(function (id) {
      var input = document.getElementById(id);
      if (!input) return;
      var label = document.querySelector('label[for="' + id + '"]');
      var br =
        label && label.nextElementSibling && label.nextElementSibling.tagName === "BR"
          ? label.nextElementSibling
          : null;
      var opt = byValue[input.value];

      if (!opt) {
        input.style.display = "none";
        input.checked = false;
        if (label) label.style.display = "none";
        if (br) br.style.display = "none";
        return;
      }

      input.style.display = "";
      if (label) {
        label.style.display = "";
        var span = label.querySelector("span");
        if (span) span.textContent = opt.label + " (" + opt.count + ")";
      }
      if (br) br.style.display = "";
    });
  }

  // Pre-checks whatever color/condition values are already active on
  // this page's product grid (e.g. after a page reload with
  // ?color=red&condition=new in the URL), so the sidebar reflects the
  // grid it's sitting next to.
  function restoreCheckedState(ids) {
    var params = new URLSearchParams(window.location.search);
    var key = ids === COLOR_IDS ? "color" : "condition";
    var active = params.getAll(key);
    ids.forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.checked = active.indexOf(input.value) !== -1;
    });
  }

  // Applies the currently-checked Color/Condition checkboxes live to
  // this page's own product grid, without touching price/category/tag/
  // sort/show, which are tracked independently by shop-list.js's state.
  function applyCheckboxFiltersLive() {
    if (!window.ShopList) return;
    window.ShopList.applyFilters({
      color: checkedValues(COLOR_IDS),
      condition: checkedValues(CONDITION_IDS),
    });
  }

  function wireCheckboxLiveFiltering(ids) {
    ids.forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.addEventListener("change", applyCheckboxFiltersLive);
    });
  }

  submitLink.addEventListener("click", function (event) {
    event.preventDefault();

    var params = new URLSearchParams();
    var minPrice = sliderPrice("slider-range-value1");
    var maxPrice = sliderPrice("slider-range-value2");
    if (minPrice !== null) params.set("min_price", minPrice);
    if (maxPrice !== null) params.set("max_price", maxPrice);

    checkedValues(COLOR_IDS).forEach(function (value) {
      params.append("color", value);
    });
    checkedValues(CONDITION_IDS).forEach(function (value) {
      params.append("condition", value);
    });

    var query = params.toString();
    window.location.href = submitLink.getAttribute("href") + (query ? "?" + query : "");
  });

  // The noUiSlider instance itself is created by main.js, which loads
  // after this script - so the range/live-update wiring below waits
  // for window "load" (after main.js has definitely run) instead of
  // assuming script order.
  window.addEventListener("load", function () {
    restoreCheckedState(COLOR_IDS);
    restoreCheckedState(CONDITION_IDS);
    wireCheckboxLiveFiltering(COLOR_IDS);
    wireCheckboxLiveFiltering(CONDITION_IDS);

    var rangeSlider = document.getElementById("slider-range");

    Api.get("products/facets/")
      .then(function (facets) {
        applyFacetOptions(COLOR_IDS, facets.colors);
        applyFacetOptions(CONDITION_IDS, facets.conditions);

        if (!rangeSlider || !rangeSlider.noUiSlider) return;
        // Real min/max from the actual product catalog (same "price"
        // field the min_price/max_price filters use), replacing the
        // hardcoded 500-1000 demo default main.js sets up.
        var rawMin = facets.price && facets.price.min;
        var rawMax = facets.price && facets.price.max;
        var hasPrices =
          rawMin !== null &&
          rawMin !== undefined &&
          rawMax !== null &&
          rawMax !== undefined &&
          !isNaN(rawMin) &&
          !isNaN(rawMax);

        if (!hasPrices) {
          // No published products to price against at all (e.g. an
          // empty catalog) - show an honest, real "$0 - $0" instead
          // of leaving main.js's unrelated demo range in place.
          rangeSlider.noUiSlider.updateOptions(
            { range: { min: 0, max: 1 }, start: [0, 0] },
            true
          );
          return;
        }

        var min = Math.floor(rawMin);
        var max = Math.ceil(rawMax);
        // noUiSlider requires range.max > range.min. When every
        // published product shares the same price, min === max is a
        // real value, not a bug - give the slider a minimal 1-unit
        // span to satisfy that constraint while keeping both handles
        // on the real price.
        var rangeMax = max > min ? max : min + 1;
        rangeSlider.noUiSlider.updateOptions(
          { range: { min: min, max: rangeMax }, start: [min, max] },
          true
        );
      })
      .catch(function () {
        // Keep the checkboxes/slider's existing defaults if this fails.
      });

    if (!rangeSlider || !rangeSlider.noUiSlider) return;

    // Apply the price range live to this page's own product grid as
    // soon as the shopper settles on a value (noUiSlider's "change"
    // event - drag/keyboard included - not every intermediate "update"
    // tick), without touching the Fillter button/color/condition above.
    rangeSlider.noUiSlider.on("change", function () {
      if (!window.ShopList) return;
      var minPrice = sliderPrice("slider-range-value1");
      var maxPrice = sliderPrice("slider-range-value2");
      window.ShopList.applyFilters({
        min_price: minPrice || "",
        max_price: maxPrice || "",
      });
    });
  });
})(window, document);
