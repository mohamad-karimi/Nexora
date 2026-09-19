(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var grid = document.querySelector(".js-product-grid");
  if (!grid) return; // page doesn't use this script's markup

  var state = {
    category: "",
    vendor: "",
    tag: "",
    q: "",
    ordering: "-created_date",
    page: 1,
    page_size: 12,
    min_price: "",
    max_price: "",
    color: [],
    condition: [],
  };

  var categoriesById = {};
  var categoriesBySlug = {};

  function readStateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    state.category = params.get("category") || "";
    state.vendor = params.get("vendor") || "";
    state.tag = params.get("tag") || "";
    state.q = params.get("q") || "";
    state.ordering = params.get("ordering") || "-created_date";
    state.page = parseInt(params.get("page"), 10) || 1;
    state.page_size = parseInt(params.get("page_size"), 10) || 12;
    state.min_price = params.get("min_price") || "";
    state.max_price = params.get("max_price") || "";
    state.color = params.getAll("color");
    state.condition = params.getAll("condition");
  }

  function pushStateToUrl() {
    var params = new URLSearchParams();
    if (state.category) params.set("category", state.category);
    if (state.vendor) params.set("vendor", state.vendor);
    if (state.tag) params.set("tag", state.tag);
    if (state.q) params.set("q", state.q);
    if (state.ordering && state.ordering !== "-created_date") params.set("ordering", state.ordering);
    if (state.page > 1) params.set("page", state.page);
    if (state.page_size !== 12) params.set("page_size", state.page_size);
    if (state.min_price) params.set("min_price", state.min_price);
    if (state.max_price) params.set("max_price", state.max_price);
    (state.color || []).forEach(function (value) { params.append("color", value); });
    (state.condition || []).forEach(function (value) { params.append("condition", value); });
    var query = params.toString();
    var url = window.location.pathname + (query ? "?" + query : "");
    window.history.replaceState({}, "", url);
  }

  function ratingWidth(avg) {
    var value = avg || 0;
    return Math.max(0, Math.min(100, (value / 5) * 100));
  }

  function productCardHtml(product) {
    var esc = Site.escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    var hasDiscount = product.is_on_sale;
    var wishClass = Site.isWishlisted(product.id) ? "active" : "";
    var badge = hasDiscount
      ? '<div class="product-badges product-badges-position product-badges-mrg"><span class="hot">-' +
        product.discount_percent +
        "%</span></div>"
      : "";
    var outOfStock = !product.in_stock;

    return (
      '<div class="col-lg-1-5 col-md-4 col-12 col-sm-6">' +
      '<div class="product-cart-wrap mb-30">' +
      '<div class="product-img-action-wrap">' +
      '<div class="product-img product-img-zoom">' +
      '<a href="' +
      url +
      '">' +
      (img ? '<img class="default-img" src="' + img + '" alt="' + esc(product.name) + '" />' : "") +
      "</a>" +
      "</div>" +
      '<div class="product-action-1">' +
      '<a aria-label="Add To Wishlist" class="action-btn js-wishlist-toggle ' +
      wishClass +
      '" href="#" data-product-id="' +
      product.id +
      '"><i class="fi-rs-heart"></i></a>' +
      '<a aria-label="Quick view" class="action-btn js-quick-view" href="#" data-product-slug="' +
      product.slug +
      '"><i class="fi-rs-eye"></i></a>' +
      "</div>" +
      badge +
      "</div>" +
      '<div class="product-content-wrap">' +
      '<div class="product-category"><a href="/shop/grid-left/?category=' +
      encodeURIComponent(product.category.slug) +
      '">' +
      esc(product.category.name) +
      "</a></div>" +
      "<h2><a href=\"" +
      url +
      '">' +
      esc(product.name) +
      "</a></h2>" +
      '<div class="product-rate-cover">' +
      '<div class="product-rate d-inline-block"><div class="product-rating" style="width: ' +
      ratingWidth(product.average_rating) +
      '%"></div></div>' +
      '<span class="font-small ml-5 text-muted"> (' +
      (product.average_rating ? product.average_rating.toFixed(1) : "0") +
      ")</span>" +
      "</div>" +
      "<div><span class=\"font-small text-muted\">By <a href=\"/shop/grid-left/?vendor=" +
      encodeURIComponent(product.vendor.slug) +
      '">' +
      esc(product.vendor.store_name) +
      "</a></span></div>" +
      '<div class="product-card-bottom">' +
      '<div class="product-price">' +
      "<span>" +
      Site.formatMoney(product.final_price) +
      "</span>" +
      (hasDiscount
        ? '<span class="old-price">' + Site.formatMoney(product.price) + "</span>"
        : "") +
      "</div>" +
      '<div class="add-cart">' +
      (outOfStock
        ? '<span class="add text-muted">Out of stock</span>'
        : '<a class="add js-add-to-cart" href="#" data-product-id="' +
          product.id +
          '"><i class="fi-rs-shopping-cart mr-5"></i>Add </a>')
      +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderProducts(data) {
    if (!data.results.length) {
      grid.innerHTML =
        '<div class="col-12 text-center py-5"><p class="mb-0">No products match your filters.</p></div>';
    } else {
      grid.innerHTML = data.results.map(productCardHtml).join("");
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
    var html = "";
    html +=
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

  function updatePageTitle() {
    var title = document.querySelector(".js-page-title");
    if (!title) return;
    if (state.category && categoriesBySlug[state.category]) {
      title.textContent = categoriesBySlug[state.category].name;
    } else if (state.q) {
      title.textContent = 'Search: "' + state.q + '"';
    } else {
      title.textContent = "Shop";
    }
  }

  function loadProducts() {
    grid.innerHTML =
      '<div class="col-12 text-center py-5"><p class="mb-0">Loading products…</p></div>';
    return Api.get("products/", {
      category: state.category || undefined,
      vendor: state.vendor || undefined,
      tag: state.tag || undefined,
      search: state.q || undefined,
      ordering: state.ordering,
      page: state.page,
      page_size: state.page_size,
      min_price: state.min_price || undefined,
      max_price: state.max_price || undefined,
      color: state.color && state.color.length ? state.color : undefined,
      condition: state.condition && state.condition.length ? state.condition : undefined,
    })
      .then(function (data) {
        renderProducts(data);
        updatePageTitle();
      })
      .catch(function (error) {
        grid.innerHTML =
          '<div class="col-12 text-center py-5 text-danger"><p class="mb-0">' +
          Site.escapeHtml(error.message || "Could not load products.") +
          "</p></div>";
      });
  }

  function loadCategories() {
    return Api.get("categories/", { page_size: 100 }).then(function (data) {
      var list = document.querySelector(".js-category-list");
      var html = "";
      data.results.forEach(function (category) {
        categoriesById[category.id] = category;
        categoriesBySlug[category.slug] = category;
        html +=
          '<li><a href="#" class="js-category-link ' +
          (state.category === category.slug ? "active" : "") +
          '" data-slug="' +
          category.slug +
          '">' +
          (category.image
            ? '<img src="' + category.image + '" alt="" />'
            : "") +
          Site.escapeHtml(category.name) +
          '</a><span class="count">' +
          category.product_count +
          "</span></li>";
      });
      if (list) list.innerHTML = html;
    });
  }

  function loadTags() {
    var list = document.querySelector(".js-tags-list");
    if (!list) return;
    Api.get("tags/", { page_size: 100 }).then(function (data) {
      var html = "";
      data.results.forEach(function (tag) {
        html +=
          '<li class="hover-up' +
          (state.tag === tag.slug ? " active" : "") +
          '"><a href="#" class="js-tag-link" data-slug="' +
          tag.slug +
          '"><i class="fi-rs-cross mr-10"></i>' +
          Site.escapeHtml(tag.name) +
          "</a></li>";
      });
      list.innerHTML = html;
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

  function loadSidebarNewProducts() {
    var container = document.querySelector(".js-sidebar-new-products");
    if (!container) return;
    Api.get("products/", { ordering: "-created_date", page_size: 3 }).then(function (data) {
      container.innerHTML = data.results
        .map(function (product) {
          return (
            '<div class="single-post clearfix"><div class="image"><a href="/shop/product/' +
            encodeURIComponent(product.slug) +
            '/">' +
            (product.image
              ? '<img src="' + product.image + '" alt="' + Site.escapeHtml(product.name) + '" />'
              : "") +
            '</a></div><div class="content pt-10"><h6><a href="/shop/product/' +
            encodeURIComponent(product.slug) +
            '/">' +
            Site.escapeHtml(product.name) +
            '</a></h6><p class="price mb-0 mt-5">' +
            Site.formatMoney(product.final_price) +
            '</p><div class="product-rate"><div class="product-rating" style="width: ' +
            ratingWidth(product.average_rating) +
            '%"></div></div></div></div>'
          );
        })
        .join("");
    });
  }

  function wireEvents() {
    document.addEventListener("click", function (event) {
      var categoryLink = event.target.closest(".js-category-link");
      if (categoryLink) {
        event.preventDefault();
        var slug = categoryLink.getAttribute("data-slug");
        state.category = state.category === slug ? "" : slug;
        state.page = 1;
        pushStateToUrl();
        document
          .querySelectorAll(".js-category-link")
          .forEach(function (a) { a.classList.toggle("active", a === categoryLink && state.category); });
        loadProducts();
        return;
      }

      var tagLink = event.target.closest(".js-tag-link");
      if (tagLink) {
        event.preventDefault();
        var tagSlug = tagLink.getAttribute("data-slug");
        state.tag = state.tag === tagSlug ? "" : tagSlug;
        state.page = 1;
        document.querySelectorAll(".js-tag-link").forEach(function (a) {
          a.closest("li").classList.toggle("active", a === tagLink && !!state.tag);
        });
        pushStateToUrl();
        loadProducts();
        return;
      }

      var pageSizeOption = event.target.closest(".js-page-size-option");
      if (pageSizeOption) {
        event.preventDefault();
        state.page_size = parseInt(pageSizeOption.getAttribute("data-value"), 10) || 12;
        state.page = 1;
        document.querySelectorAll(".js-page-size-option").forEach(function (a) {
          a.classList.toggle("active", a === pageSizeOption);
        });
        var label = document.querySelector(".js-page-size-label");
        if (label) label.innerHTML = " " + pageSizeOption.textContent + ' <i class="fi-rs-angle-small-down"></i>';
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

      // Wishlist toggle / add-to-cart on product cards are handled
      // sitewide by site.js (wireProductActions), so every page that
      // renders a .js-wishlist-toggle / .js-add-to-cart button gets
      // the same behaviour without each page script re-wiring it.
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    readStateFromUrl();
    wireEvents();
    Site.ready().then(function () {
      loadCategories().then(function () {
        updatePageTitle();
      });
      loadTags();
      loadProducts();
      loadOnSaleProducts();
      loadSidebarNewProducts();
    });
  });

  // Small integration point so other page-specific scripts (currently
  // sidebar-price-filter.js, for the price slider and the Color /
  // Item Condition checkboxes) can apply an extra filter to this same
  // grid/state without duplicating the request/render/URL-sync logic
  // above.
  window.ShopList = {
    applyFilters: function (patch) {
      Object.keys(patch).forEach(function (key) {
        state[key] = patch[key];
      });
      state.page = 1;
      pushStateToUrl();
      loadProducts();
    },
    // Read-only snapshot so a page script can restore checkbox state
    // (e.g. after navigating back with ?color=red already in the URL)
    // without reaching into this closure's private `state` object.
    getState: function () {
      return {
        min_price: state.min_price,
        max_price: state.max_price,
        color: (state.color || []).slice(),
        condition: (state.condition || []).slice(),
      };
    },
  };
})(window, document);
