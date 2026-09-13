/**
 * Populates the "Category" and "Trending Now" widgets in
 * templates/website/sidebar.html (included on the purchase-guide,
 * terms, and privacy-policy pages) with live data from the API.
 *
 * The markup used to ship with hardcoded demo categories/products
 * whose links pointed at "shop-grid-right.html" and at the original
 * HTML theme's external demo site (nest-frontend-v6.vercel.app) -
 * dead ends inside this Django project. This mirrors the same
 * categories/new-products loading already used on the shop listing
 * pages (see static/js/pages/shop-list.js) so the widgets show real
 * data and link to real pages.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  function ratingWidth(avg) {
    var value = avg || 0;
    return Math.max(0, Math.min(100, (value / 5) * 100));
  }

  function loadCategories() {
    var list = document.querySelector(".js-category-list");
    if (!list) return;

    Api.get("categories/", { page_size: 100 }).then(function (data) {
      list.innerHTML = data.results
        .map(function (category) {
          return (
            '<li><a href="/shop/grid-left/?category=' +
            encodeURIComponent(category.slug) +
            '">' +
            (category.image
              ? '<img src="' + category.image + '" alt="" />'
              : "") +
            Site.escapeHtml(category.name) +
            '</a><span class="count">' +
            category.product_count +
            "</span></li>"
          );
        })
        .join("");
    });
  }

  function loadNewProducts() {
    var container = document.querySelector(".js-sidebar-new-products");
    if (!container) return;

    Api.get("products/", { ordering: "-created_date", page_size: 4 }).then(
      function (data) {
        container.innerHTML = data.results
          .map(function (product) {
            var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
            return (
              '<div class="single-post clearfix"><div class="image"><a href="' +
              url +
              '">' +
              (product.image
                ? '<img src="' +
                  product.image +
                  '" alt="' +
                  Site.escapeHtml(product.name) +
                  '" />'
                : "") +
              '</a></div><div class="content pt-10"><h6><a href="' +
              url +
              '">' +
              Site.escapeHtml(product.name) +
              '</a></h6><p class="price mb-0 mt-5">' +
              Site.formatMoney(product.final_price) +
              '</p><div class="product-rate"><div class="product-rating" style="width: ' +
              ratingWidth(product.average_rating) +
              '%"></div></div></div></div>'
            );
          })
          .join("");
      }
    );
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadCategories();
    loadNewProducts();
  });
})(window, document);
