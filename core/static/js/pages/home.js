/**
 * Home page (website/index.html) dynamic product sections.
 *
 * The catalog has no "units sold" / "trending" tracking, so a couple
 * of section labels inherited from the theme ("Top Selling",
 * "Trending Products", the "Popular"/"Featured" best-sells tabs) are
 * mapped onto the closest real signal the API exposes (rating,
 * price, recency) rather than fabricated numbers. Everything else
 * (categories, on-sale deals, recently added, top rated) uses its
 * exact real field.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var popularNav = document.querySelector(".js-popular-tabs-nav");
  var popularContent = document.querySelector(".js-popular-tabs-content");

  function productGridHtml(products) {
    if (!products.length) {
      return '<div class="col-12 text-center py-4"><p class="mb-0">No products yet.</p></div>';
    }
    return products.map(Site.buildProductCard).join("");
  }

  function loadPopularProductsTabs() {
    if (!popularNav || !popularContent) return;

    Promise.all([
      Api.get("products/", { ordering: "-created_date", page_size: 10 }),
      Api.get("categories/", { page_size: 5, ordering: "name" }),
    ]).then(function (results) {
      var allProducts = results[0];
      var categories = results[1].results;

      var tabs = [{ id: "all", label: "All", products: allProducts.results }];
      categories.forEach(function (category) {
        tabs.push({ id: "cat-" + category.id, label: category.name, slug: category.slug });
      });

      popularNav.innerHTML = tabs
        .map(function (tab, index) {
          return (
            '<li class="nav-item" role="presentation">' +
            '<button class="nav-link ' +
            (index === 0 ? "active" : "") +
            '" id="nav-tab-' +
            tab.id +
            '" data-bs-toggle="tab" data-bs-target="#tab-' +
            tab.id +
            '" type="button" role="tab" aria-controls="tab-' +
            tab.id +
            '" aria-selected="' +
            (index === 0 ? "true" : "false") +
            '">' +
            Site.escapeHtml(tab.label) +
            "</button></li>"
          );
        })
        .join("");

      popularContent.innerHTML = tabs
        .map(function (tab, index) {
          return (
            '<div class="tab-pane fade ' +
            (index === 0 ? "show active" : "") +
            '" id="tab-' +
            tab.id +
            '" role="tabpanel" aria-labelledby="tab-' +
            tab.id +
            '">' +
            '<div class="row product-grid-4">' +
            (index === 0 ? productGridHtml(tab.products) : '<div class="col-12 text-center py-4">Loading…</div>') +
            "</div></div>"
          );
        })
        .join("");

      // Lazily fetch each category tab's products the first time it is shown.
      tabs.slice(1).forEach(function (tab) {
        var button = document.getElementById("nav-tab-" + tab.id);
        var pane = document.getElementById("tab-" + tab.id);
        if (!button || !pane) return;
        var loaded = false;
        button.addEventListener("shown.bs.tab", function () {
          if (loaded) return;
          loaded = true;
          Api.get("products/", { category: tab.slug, ordering: "-created_date", page_size: 10 }).then(function (data) {
            pane.querySelector(".row").innerHTML = productGridHtml(data.results);
          });
        });
      });
    });
  }

  function loadBestSalesTabs() {
    var orderingByTab = {
      featured: "-average_rating",
      popular: "-price",
      new: "-created_date",
    };
    document.querySelectorAll(".js-best-sales-tab").forEach(function (container) {
      var tab = container.getAttribute("data-tab");
      Api.get("products/", { ordering: orderingByTab[tab] || "-created_date", page_size: 10 }).then(function (data) {
        container.innerHTML = productGridHtml(data.results);
      });
    });
  }

  function loadOnSaleProducts() {
    var container = document.querySelector(".js-onsale-products");
    if (!container) return;
    Api.get("products/", { ordering: "-created_date", page_size: 50 }).then(function (data) {
      var onSale = data.results.filter(function (p) { return p.is_on_sale; }).slice(0, 4);
      container.innerHTML = onSale.length
        ? onSale.map(Site.buildDealCard).join("")
        : '<div class="col-12 text-center py-4"><p class="mb-0">No active deals right now.</p></div>';
    });
  }

  function loadFooterWidgets() {
    var orderingByWidget = {
      top_selling: "-price",
      trending: "-average_rating",
      recent: "-created_date",
      top_rated: "-average_rating",
    };
    document.querySelectorAll(".js-footer-widget").forEach(function (container) {
      var widget = container.getAttribute("data-widget");
      // "trending" and "top_rated" share an ordering; use different
      // pages so the two widgets don't show the exact same 3 items.
      var page = widget === "trending" ? 2 : 1;
      Api.get("products/", {
        ordering: orderingByWidget[widget] || "-created_date",
        page_size: 3,
        page: page,
      }).then(function (data) {
        container.innerHTML = data.results.length
          ? data.results.map(Site.buildMiniCard).join("")
          : "";
      });
    });
  }

  function loadFeaturedCategories() {
    var nav = document.querySelector(".js-featured-categories-nav");
    var grid = document.querySelector(".js-featured-categories");
    if (!nav || !grid) return;

    var bgClasses = ["bg-9", "bg-10", "bg-11", "bg-12", "bg-13", "bg-14", "bg-15"];
    var delays = [".1s", ".2s", ".3s", ".4s", ".5s", ".6s", ".7s", ".8s", ".9s", "1s"];

    Api.get("categories/", { page_size: 12, ordering: "name" }).then(function (data) {
      var categories = data.results;
      if (!categories.length) return;

      nav.innerHTML = categories
        .map(function (category, index) {
          return (
            '<li class="list-inline-item nav-item"><a class="nav-link ' +
            (index === 0 ? "active" : "") +
            '" href="/shop/filter/?category=' +
            encodeURIComponent(category.slug) +
            '">' +
            Site.escapeHtml(category.name) +
            "</a></li>"
          );
        })
        .join("");

      grid.innerHTML = categories
        .map(function (category, index) {
          var url = "/shop/filter/?category=" + encodeURIComponent(category.slug);
          return (
            '<div class="col-lg-2 col-md-4 col-6 mb-4">' +
            '<div class="card-2 ' +
            bgClasses[index % bgClasses.length] +
            ' wow animate__animated animate__fadeInUp" data-wow-delay="' +
            delays[index % delays.length] +
            '">' +
            '<figure class="img-hover-scale overflow-hidden">' +
            '<a href="' +
            url +
            '">' +
            (category.image ? '<img src="' + category.image + '" alt="" />' : "") +
            "</a>" +
            "</figure>" +
            "<h6><a href=\"" +
            url +
            '">' +
            Site.escapeHtml(category.name) +
            "</a></h6>" +
            "<span>" +
            category.product_count +
            " items</span>" +
            "</div>" +
            "</div>"
          );
        })
        .join("");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(function () {
      loadFeaturedCategories();
      loadPopularProductsTabs();
      loadBestSalesTabs();
      loadOnSaleProducts();
      loadFooterWidgets();
    });
  });
})(window, document);
