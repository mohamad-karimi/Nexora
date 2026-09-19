/**
 * shop-compare.html - side-by-side product comparison.
 *
 * There is no "compare list" API in the project, so the list of
 * product ids being compared is kept client-side in localStorage
 * (this is a pure UI convenience, same as most storefront themes) -
 * the actual product data always comes live from the existing
 * /api/v1/products/ endpoint, never fabricated.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var body = document.querySelector(".js-compare-body");
  if (!body) return;

  var STORAGE_KEY = "nexora_compare_ids";
  var MAX_ITEMS = 4;

  function getStoredIds() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return Array.isArray(raw) ? raw.filter(function (n) { return Number.isInteger(n); }) : [];
    } catch (e) {
      return [];
    }
  }

  function saveIds(ids) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  }

  function addFromQueryString(ids) {
    var params = new URLSearchParams(window.location.search);
    var addId = parseInt(params.get("add"), 10);
    if (addId) {
      ids = ids.filter(function (id) { return id !== addId; });
      ids.unshift(addId);
      if (ids.length > MAX_ITEMS) ids = ids.slice(0, MAX_ITEMS);
    }
    window.history.replaceState({}, "", window.location.pathname);
    return ids;
  }

  function render(products) {
    document.querySelectorAll(".js-compare-count").forEach(function (el) {
      el.textContent = products.length;
    });

    var emptyState = document.querySelector(".js-compare-empty");
    var table = body.closest("table");

    if (!products.length) {
      body.innerHTML = "";
      if (table) table.closest(".table-responsive").style.display = "none";
      if (emptyState) emptyState.style.display = "";
      return;
    }
    if (table) table.closest(".table-responsive").style.display = "";
    if (emptyState) emptyState.style.display = "none";

    function row(label, cellsHtml) {
      return (
        '<tr><td class="text-muted font-sm fw-600 font-heading mw-200">' +
        label +
        "</td>" +
        cellsHtml.join("") +
        "</tr>"
      );
    }

    var esc = Site.escapeHtml;

    var previewCells = products.map(function (p) {
      return (
        '<td class="row_img"><a href="/shop/product/' +
        encodeURIComponent(p.slug) +
        '/"><img src="' +
        (p.image || "") +
        '" alt="' +
        esc(p.name) +
        '" /></a></td>'
      );
    });
    var nameCells = products.map(function (p) {
      return (
        '<td class="product_name"><h6><a href="/shop/product/' +
        encodeURIComponent(p.slug) +
        '/" class="text-heading">' +
        esc(p.name) +
        "</a></h6></td>"
      );
    });
    var priceCells = products.map(function (p) {
      return '<td class="product_price"><h4 class="price text-brand">' + Site.formatMoney(p.final_price) + "</h4></td>";
    });
    var ratingCells = products.map(function (p) {
      return (
        '<td><div class="rating_wrap"><div class="product-rate d-inline-block"><div class="product-rating" style="width: ' +
        Site.ratingWidth(p.average_rating) +
        '%"></div></div><span class="rating_num">(' +
        p.review_count +
        ")</span></div></td>"
      );
    });
    var categoryCells = products.map(function (p) {
      return "<td>" + esc(p.category.name) + "</td>";
    });
    var vendorCells = products.map(function (p) {
      return "<td>" + esc(p.vendor.store_name) + "</td>";
    });
    var descriptionCells = products.map(function (p) {
      return '<td class="row_text font-xs"><p class="font-sm text-muted">' + esc(p.short_description || "") + "</p></td>";
    });
    var stockCells = products.map(function (p) {
      return p.in_stock
        ? '<td class="row_stock"><span class="stock-status in-stock mb-0">In Stock</span></td>'
        : '<td class="row_stock"><span class="stock-status out-stock mb-0">Out of stock</span></td>';
    });
    var buyCells = products.map(function (p) {
      return p.in_stock
        ? '<td class="row_btn"><button class="btn btn-sm js-add-to-cart" data-product-id="' +
          p.id +
          '"><i class="fi-rs-shopping-bag mr-5"></i>Add to cart</button></td>'
        : '<td class="row_btn"><button class="btn btn-sm btn-secondary" disabled><i class="fi-rs-shopping-bag mr-5"></i>Out of stock</button></td>';
    });
    var removeCells = products.map(function (p) {
      return (
        '<td class="row_remove"><a href="#" class="text-muted js-compare-remove" data-product-id="' +
        p.id +
        '"><i class="fi-rs-trash mr-5"></i><span>Remove</span></a></td>'
      );
    });

    body.innerHTML =
      row("Preview", previewCells) +
      row("Name", nameCells) +
      row("Price", priceCells) +
      row("Rating", ratingCells) +
      row("Category", categoryCells) +
      row("Vendor", vendorCells) +
      row("Description", descriptionCells) +
      row("Stock status", stockCells) +
      row("Buy now", buyCells) +
      row("", removeCells);
  }

  function loadAndRender() {
    var ids = addFromQueryString(getStoredIds());
    saveIds(ids);

    if (!ids.length) {
      render([]);
      return;
    }

    Api.get("products/", { page_size: 200 }).then(function (data) {
      var byId = {};
      data.results.forEach(function (p) {
        byId[p.id] = p;
      });
      var found = ids.filter(function (id) { return byId[id]; });
      if (found.length !== ids.length) saveIds(found);
      render(found.map(function (id) { return byId[id]; }));
    });
  }

  document.addEventListener("click", function (event) {
    var removeBtn = event.target.closest(".js-compare-remove");
    if (removeBtn) {
      event.preventDefault();
      var id = parseInt(removeBtn.getAttribute("data-product-id"), 10);
      var ids = getStoredIds().filter(function (existing) { return existing !== id; });
      saveIds(ids);
      loadAndRender();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(loadAndRender);
  });
})(window, document);
