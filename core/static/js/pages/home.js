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
    // Deepest discount first: the API applies the ordering
    // (discount_percent, descending), we only display what it returns.
    // is_on_sale still needs a client-side check because it also
    // accounts for discount_end (an expired discount keeps its old
    // discount_percent but is no longer actually "on sale").
    Api.get("products/", { ordering: "-discount_percent", page_size: 50 }).then(function (data) {
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

  /**
   * Hero slider ("home-slider" section). The template ships the
   * original 2 static slides as a fallback so `main.js`'s unconditional
   * `$(".hero-slider-1").slick(...)` call (which runs synchronously,
   * before this page's async API calls can possibly resolve) always
   * has something valid to initialize on. Once the real slide data
   * arrives, the running Slick instance is torn down and rebuilt with
   * the same options main.js used, now showing the DB-backed slides.
   */
  function slideHtml(slide) {
    var esc = Site.escapeHtml;
    var titleHtml = String(slide.title || "").split("\n").map(esc).join("<br />");
    return (
      '<div class="single-hero-slider single-animation-wrap" style="background-image: url(' +
      (slide.image || "") +
      ')">' +
      '<div class="slider-content">' +
      '<h1 class="display-2 mb-40">' +
      titleHtml +
      "</h1>" +
      (slide.description ? '<p class="mb-65">' + esc(slide.description) + "</p>" : "") +
      "</div>" +
      "</div>"
    );
  }

  function loadHeroSlider() {
    var wrap = document.querySelector(".hero-slider-1");
    if (!wrap) return;
    Api.get("home-slides/").then(function (slides) {
      if (!slides || !slides.length) return; // keep the fallback slides already in the DOM
      var jq = window.jQuery;
      var isSlick = jq && jq.fn && jq.fn.slick && jq(wrap).hasClass("slick-initialized");
      if (isSlick) jq(wrap).slick("unslick");
      wrap.innerHTML = slides.map(slideHtml).join("");
      if (jq && jq.fn && jq.fn.slick) {
        jq(wrap).slick({
          slidesToShow: 1,
          slidesToScroll: 1,
          fade: true,
          loop: true,
          dots: true,
          arrows: true,
          prevArrow: '<span class="slider-btn slider-prev"><i class="fi-rs-angle-left"></i></span>',
          nextArrow: '<span class="slider-btn slider-next"><i class="fi-rs-angle-right"></i></span>',
          appendArrows: ".hero-slider-1-arrow",
          autoplay: true,
        });
      }
    });
  }

  /**
   * Banners 3-up ("banners mb-25" section). The row is empty in the
   * template (same pattern as .js-featured-categories) since, unlike
   * the hero slider, nothing else on the page initializes against
   * this markup, so it's safe to render it purely from the API.
   * Only the first 3 active banners are used -- the layout is a fixed
   * 3-column row -- and each position keeps its original column/delay
   * classes so the responsive behaviour is unchanged.
   */
  var BANNER_COL_CLASSES = ["col-lg-4 col-md-6", "col-lg-4 col-md-6", "col-lg-4 d-md-none d-lg-flex"];
  var BANNER_DELAYS = ["0", ".2s", ".4s"];

  function bannerHtml(banner, index) {
    var esc = Site.escapeHtml;
    var titleHtml = String(banner.title || "").split("\n").map(esc).join("<br />");
    var url = banner.link_url || "/shop/filter/";
    var colClass = BANNER_COL_CLASSES[index];
    var delay = BANNER_DELAYS[index];
    var imgClass = index === 2 ? "banner-img mb-sm-0" : "banner-img";
    return (
      '<div class="' +
      colClass +
      '">' +
      '<div class="' +
      imgClass +
      ' wow animate__animated animate__fadeInUp" data-wow-delay="' +
      delay +
      '">' +
      (banner.image ? '<img src="' + banner.image + '" alt="" />' : "") +
      '<div class="banner-text">' +
      "<h4>" +
      titleHtml +
      "</h4>" +
      '<a href="' +
      esc(url) +
      '" class="btn btn-xs">Shop Now <i class="fi-rs-arrow-small-right"></i></a>' +
      "</div></div></div>"
    );
  }

  function loadBanners() {
    var row = document.querySelector(".js-home-banners");
    if (!row) return;
    Api.get("home-banners/").then(function (banners) {
      row.innerHTML = (banners || []).slice(0, 3).map(bannerHtml).join("");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(function () {
      loadHeroSlider();
      loadFeaturedCategories();
      loadBanners();
      loadPopularProductsTabs();
      loadBestSalesTabs();
      loadOnSaleProducts();
      loadFooterWidgets();
    });
  });
})(window, document);
