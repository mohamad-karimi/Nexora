/**
 * shop-filter.html - the fully-featured product listing page.
 * Same architecture/conventions as shop-list.js (used by
 * shop-grid-left.html): filter state lives in one object, is
 * read from / written to the URL query string, and every change
 * re-fetches /api/v1/products/ with the matching query params.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var grid = document.querySelector(".js-product-grid");
  if (!grid) return;

  var state = {
    category: "",
    vendor: "",
    tag: "",
    min_price: "",
    max_price: "",
    in_stock: "",
    color: [],
    condition: [],
    q: "",
    ordering: "name",
    page: 1,
    page_size: 50,
  };

  function readStateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    state.category = params.get("category") || "";
    state.vendor = params.get("vendor") || "";
    state.tag = params.get("tag") || "";
    state.min_price = params.get("min_price") || "";
    state.max_price = params.get("max_price") || "";
    state.in_stock = params.get("in_stock") || "";
    state.color = params.getAll("color");
    state.condition = params.getAll("condition");
    state.q = params.get("q") || "";
    state.ordering = params.get("ordering") || "name";
    state.page = parseInt(params.get("page"), 10) || 1;
    state.page_size = parseInt(params.get("page_size"), 10) || 50;
  }

  function pushStateToUrl() {
    var params = new URLSearchParams();
    if (state.category) params.set("category", state.category);
    if (state.vendor) params.set("vendor", state.vendor);
    if (state.tag) params.set("tag", state.tag);
    if (state.min_price) params.set("min_price", state.min_price);
    if (state.max_price) params.set("max_price", state.max_price);
    if (state.in_stock) params.set("in_stock", state.in_stock);
    state.color.forEach(function (value) {
      params.append("color", value);
    });
    state.condition.forEach(function (value) {
      params.append("condition", value);
    });
    if (state.q) params.set("q", state.q);
    if (state.ordering && state.ordering !== "name") params.set("ordering", state.ordering);
    if (state.page > 1) params.set("page", state.page);
    if (state.page_size !== 50) params.set("page_size", state.page_size);
    var query = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (query ? "?" + query : ""));
  }

  function renderProducts(data) {
    if (!data.results.length) {
      grid.innerHTML =
        '<div class="col-12 text-center py-5"><p class="mb-0">No products match your filters.</p></div>';
    } else {
      grid.innerHTML = data.results.map(Site.buildProductCard).join("");
    }
    document.querySelectorAll(".js-result-count").forEach(function (el) {
      el.textContent = data.count;
    });
    renderPagination(data.count);
  }

  function renderPagination(count) {
    var container = document.querySelector(".js-pagination");
    if (!container) return;
    var totalPages = Math.max(1, Math.ceil(count / state.page_size));
    if (totalPages <= 1) {
      container.innerHTML = "";
      return;
    }
    var html =
      '<li class="page-item"><a class="page-link js-page-link" data-page="' +
      Math.max(1, state.page - 1) +
      '" href="#"><i class="fi-rs-arrow-small-left"></i></a></li>';

    var start = Math.max(1, state.page - 2);
    var end = Math.min(totalPages, start + 4);
    start = Math.max(1, Math.min(start, end - 4));

    for (var p = start; p <= end; p++) {
      html +=
        '<li class="page-item ' +
        (p === state.page ? "active" : "") +
        '"><a class="page-link js-page-link" data-page="' +
        p +
        '" href="#">' +
        p +
        "</a></li>";
    }
    html +=
      '<li class="page-item"><a class="page-link js-page-link" data-page="' +
      Math.min(totalPages, state.page + 1) +
      '" href="#"><i class="fi-rs-arrow-small-right"></i></a></li>';
    container.innerHTML = html;
  }

  function loadProducts() {
    grid.innerHTML =
      '<div class="col-12 text-center py-5"><p class="mb-0">Loading products…</p></div>';
    return Api.get("products/", {
      category: state.category || undefined,
      vendor: state.vendor || undefined,
      tag: state.tag || undefined,
      min_price: state.min_price || undefined,
      max_price: state.max_price || undefined,
      in_stock: state.in_stock || undefined,
      color: state.color,
      condition: state.condition,
      search: state.q || undefined,
      ordering: state.ordering,
      page: state.page,
      page_size: state.page_size,
    })
      .then(renderProducts)
      .catch(function (error) {
        grid.innerHTML =
          '<div class="col-12 text-center py-5 text-danger"><p class="mb-0">' +
          Site.escapeHtml(error.message || "Could not load products.") +
          "</p></div>";
      });
  }

  function loadCategories() {
    var list = document.querySelector(".js-category-list");
    if (!list) return Promise.resolve();
    return Api.get("categories/", { page_size: 100 }).then(function (data) {
      list.innerHTML = data.results
        .map(function (category) {
          return (
            '<li><a href="#" class="js-category-link ' +
            (state.category === category.slug ? "active" : "") +
            '" data-slug="' +
            category.slug +
            '">' +
            (category.image ? '<img src="' + category.image + '" alt="" />' : "") +
            Site.escapeHtml(category.name) +
            ' <span class="text-muted">(' +
            category.product_count +
            ")</span></a></li>"
          );
        })
        .join("");
    });
  }

  function loadVendors() {
    var list = document.querySelector(".js-vendor-list");
    if (!list) return Promise.resolve();
    return Api.get("vendors/", { page_size: 100, ordering: "store_name" }).then(function (data) {
      list.innerHTML = data.results
        .map(function (vendor) {
          return (
            '<li><a href="#" class="js-vendor-link ' +
            (state.vendor === vendor.slug ? "active" : "") +
            '" data-slug="' +
            vendor.slug +
            '">' +
            (vendor.logo ? '<img src="' + vendor.logo + '" alt="" />' : "") +
            Site.escapeHtml(vendor.store_name) +
            ' <span class="text-muted">(' +
            vendor.product_count +
            ")</span></a></li>"
          );
        })
        .join("");
    });
  }

  function loadTags() {
    var list = document.querySelector(".js-tag-list");
    if (!list) return Promise.resolve();
    return Api.get("tags/", { page_size: 100 }).then(function (data) {
      list.innerHTML = data.results
        .map(function (tag) {
          return (
            '<li class="hover-up"><a href="#" class="js-tag-link ' +
            (state.tag === tag.slug ? "active" : "") +
            '" data-slug="' +
            tag.slug +
            '"><i class="fi-rs-cross mr-10"></i>' +
            Site.escapeHtml(tag.name) +
            "</a></li>"
          );
        })
        .join("");
    });
  }

  function loadOnSaleProducts() {
    var section = document.querySelector(".js-onsale-section");
    var container = document.querySelector(".js-onsale-products");
    if (!section || !container) return;
    // Deepest discount first: the API applies the ordering
    // (discount_percent, descending), we only display what it returns.
    // is_on_sale still needs a client-side check because it also
    // accounts for discount_end (an expired discount keeps its old
    // discount_percent but is no longer actually "on sale").
    Api.get("products/", { ordering: "-discount_percent", page_size: 50 }).then(function (data) {
      var onSale = data.results.filter(function (p) {
        return p.is_on_sale;
      }).slice(0, 4);
      if (!onSale.length) return;
      container.innerHTML = onSale.map(Site.buildDealCard).join("");
      section.style.display = "";
    });
  }

  function syncFilterUi() {
    document.querySelectorAll(".js-category-link").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-slug") === state.category);
    });
    document.querySelectorAll(".js-vendor-link").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-slug") === state.vendor);
    });
    document.querySelectorAll(".js-tag-link").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-slug") === state.tag);
    });
    document.querySelectorAll(".js-price-option").forEach(function (input) {
      var isActive =
        state.min_price !== "" &&
        String(input.getAttribute("data-min")) === String(state.min_price) &&
        String(input.getAttribute("data-max") || "") === String(state.max_price || "");
      input.checked = isActive;
    });
    var stockInput = document.querySelector(".js-stock-option");
    if (stockInput) stockInput.checked = state.in_stock === "true";
  }

  function wireEvents() {
    document.addEventListener("click", function (event) {
      var categoryLink = event.target.closest(".js-category-link");
      if (categoryLink) {
        event.preventDefault();
        var cSlug = categoryLink.getAttribute("data-slug");
        state.category = state.category === cSlug ? "" : cSlug;
        state.page = 1;
        pushStateToUrl();
        syncFilterUi();
        loadProducts();
        return;
      }

      var vendorLink = event.target.closest(".js-vendor-link");
      if (vendorLink) {
        event.preventDefault();
        var vSlug = vendorLink.getAttribute("data-slug");
        state.vendor = state.vendor === vSlug ? "" : vSlug;
        state.page = 1;
        pushStateToUrl();
        syncFilterUi();
        loadProducts();
        return;
      }

      var tagLink = event.target.closest(".js-tag-link");
      if (tagLink) {
        event.preventDefault();
        var tSlug = tagLink.getAttribute("data-slug");
        state.tag = state.tag === tSlug ? "" : tSlug;
        state.page = 1;
        pushStateToUrl();
        syncFilterUi();
        loadProducts();
        return;
      }

      var pageSizeOption = event.target.closest(".js-page-size-option");
      if (pageSizeOption) {
        event.preventDefault();
        state.page_size = parseInt(pageSizeOption.getAttribute("data-value"), 10) || 50;
        state.page = 1;
        document.querySelectorAll(".js-page-size-option").forEach(function (a) {
          a.classList.toggle("active", a === pageSizeOption);
        });
        var sizeLabel = document.querySelector(".js-page-size-label");
        if (sizeLabel) sizeLabel.innerHTML = " " + pageSizeOption.textContent + ' <i class="fi-rs-angle-small-down"></i>';
        pushStateToUrl();
        loadProducts();
        return;
      }

      var sortOption = event.target.closest(".js-sort-option");
      if (sortOption) {
        event.preventDefault();
        state.ordering = sortOption.getAttribute("data-value");
        state.page = 1;
        document.querySelectorAll(".js-sort-option").forEach(function (a) {
          a.classList.toggle("active", a === sortOption);
        });
        var sortLabel = document.querySelector(".js-sort-label");
        if (sortLabel) sortLabel.innerHTML = " " + sortOption.textContent + ' <i class="fi-rs-angle-small-down"></i>';
        pushStateToUrl();
        loadProducts();
        return;
      }

      var pageLink = event.target.closest(".js-page-link");
      if (pageLink) {
        event.preventDefault();
        state.page = parseInt(pageLink.getAttribute("data-page"), 10) || 1;
        pushStateToUrl();
        loadProducts();
        window.scrollTo({ top: grid.offsetTop - 100, behavior: "smooth" });
        return;
      }
    });

    document.addEventListener("change", function (event) {
      var priceOption = event.target.closest(".js-price-option");
      if (priceOption) {
        if (priceOption.checked) {
          document.querySelectorAll(".js-price-option").forEach(function (input) {
            if (input !== priceOption) input.checked = false;
          });
          state.min_price = priceOption.getAttribute("data-min") || "";
          state.max_price = priceOption.getAttribute("data-max") || "";
        } else {
          state.min_price = "";
          state.max_price = "";
        }
        state.page = 1;
        pushStateToUrl();
        loadProducts();
        return;
      }

      var stockOption = event.target.closest(".js-stock-option");
      if (stockOption) {
        state.in_stock = stockOption.checked ? "true" : "";
        state.page = 1;
        pushStateToUrl();
        loadProducts();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    readStateFromUrl();
    wireEvents();
    Site.ready().then(function () {
      Promise.all([loadCategories(), loadVendors(), loadTags()]).then(syncFilterUi);
      syncFilterUi();
      loadProducts();
      loadOnSaleProducts();
    });
  });
})(window, document);
