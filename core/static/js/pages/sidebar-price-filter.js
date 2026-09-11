/**
 * Wires up the sidebar's "Fill by price" widget (templates/shop/sidebar.html):
 * the price slider, the Color checkboxes, the Item Condition checkboxes,
 * and the "Fillter" button - exactly as designed in the original markup,
 * no UI added or removed.
 *
 * The widget has never done live filtering on this page (only the
 * slider had cosmetic JS); its "Fillter" button always linked out to
 * a results page. So clicking it now collects whatever is currently
 * selected (price range from the slider, checked colors, checked
 * conditions) and sends the shopper to the real, fully-filterable
 * listing page (shop:filter) with those as query params.
 */
(function (window, document) {
  "use strict";

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
})(window, document);
