(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var ordersBody = document.querySelector(".js-vendor-orders-body");
  if (!ordersBody) return; // not the vendor dashboard page

  var PRODUCTS_PAGE_SIZE = 10;
  var productsGrid = document.querySelector(".js-vendor-products-grid");
  var productsPagination = document.querySelector(".js-vendor-products-pagination");
  var bestSellers = document.querySelector(".js-vendor-best-sellers");

  function loadOrders() {
    Api.get("vendors/dashboard/orders/", { page_size: 8 })
      .then(function (data) {
        var results = data.results || [];
        if (!results.length) {
          ordersBody.innerHTML =
            '<tr><td colspan="5">No orders for your products yet.</td></tr>';
          return;
        }
        ordersBody.innerHTML = results
          .map(function (item) {
            return (
              "<tr><td>" +
              Site.escapeHtml(item.order_number) +
              "</td><td>" +
              new Date(item.order_date).toLocaleDateString() +
              "</td><td>" +
              Site.escapeHtml(item.order_status) +
              "</td><td>" +
              Site.formatMoney(item.total_price) +
              " for " +
              item.quantity +
              ' item</td><td><a href="#" class="btn-small d-block">View</a></td></tr>'
            );
          })
          .join("");
      })
      .catch(function () {
        ordersBody.innerHTML =
          '<tr><td colspan="5">Could not load your orders right now.</td></tr>';
      });
  }

  function bestSellerHtml(product) {
    var esc = Site.escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    return (
      '<div class="single-post clearfix">' +
      (img
        ? '<div class="image"><img src="' + img + '" alt="' + esc(product.name) + '" /></div>'
        : "") +
      '<div class="content pt-10">' +
      "<h6><a href=\"" +
      url +
      '">' +
      esc(product.name) +
      "</a></h6>" +
      '<p class="price mb-0 mt-5">' +
      Site.formatMoney(product.final_price) +
      "</p>" +
      '<div class="product-rate">' +
      '<div class="product-rating" style="width: ' +
      Site.ratingWidth(product.average_rating) +
      '%"></div>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function loadBestSellers() {
    if (!bestSellers) return;
    Api.get("vendors/dashboard/best-sellers/")
      .then(function (data) {
        var results = data.results || data;
        if (!results || !results.length) {
          bestSellers.innerHTML = '<p class="mb-0">No sales yet.</p>';
          return;
        }
        bestSellers.innerHTML = results.map(bestSellerHtml).join("");
      })
      .catch(function () {
        bestSellers.innerHTML = '<p class="mb-0">Could not load your best sellers.</p>';
      });
  }

  function productCardHtml(product) {
    var esc = Site.escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    var badge = product.is_on_sale
      ? '<div class="product-badges product-badges-position product-badges-mrg"><span class="hot">-' +
        product.discount_percent +
        "%</span></div>"
      : "";
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
      '<a aria-label="Add To Wishlist" class="action-btn" href="/shop/wishlist/"><i class="fi-rs-heart"></i></a>' +
      '<a aria-label="Compare" class="action-btn" href="/shop/compare/"><i class="fi-rs-shuffle"></i></a>' +
      '<a aria-label="Quick view" class="action-btn" data-bs-toggle="modal" data-bs-target="#quickViewModal"><i class="fi-rs-eye"></i></a>' +
      "</div>" +
      badge +
      "</div>" +
      '<div class="product-content-wrap">' +
      '<div class="product-category"><a href="/shop/filter/?category=' +
      encodeURIComponent(product.category.slug) +
      '">' +
      esc(product.category.name) +
      "</a></div>" +
      '<h2><a href="' +
      url +
      '">' +
      esc(product.name) +
      "</a></h2>" +
      '<div class="product-rate-cover">' +
      '<div class="product-rate d-inline-block"><div class="product-rating" style="width: ' +
      Site.ratingWidth(product.average_rating) +
      '%"></div></div>' +
      '<span class="font-small ml-5 text-muted"> (' +
      (product.average_rating ? product.average_rating.toFixed(1) : "0") +
      ")</span>" +
      "</div>" +
      '<div><span class="font-small text-muted">By <a href="/shop/filter/?vendor=' +
      encodeURIComponent(product.vendor.slug) +
      '">' +
      esc(product.vendor.store_name) +
      "</a></span></div>" +
      '<div class="product-card-bottom">' +
      '<div class="product-price">' +
      "<span>" +
      Site.formatMoney(product.final_price) +
      "</span>" +
      (product.is_on_sale
        ? '<span class="old-price">' + Site.formatMoney(product.price) + "</span>"
        : "") +
      "</div>" +
      '<div class="add-cart">' +
      '<a class="add" href="' +
      url +
      '"><i class="fi-rs-edit mr-5"></i>Edit </a>' +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderPagination(page, data) {
    if (!productsPagination) return;
    var totalPages = Math.max(1, Math.ceil(data.count / PRODUCTS_PAGE_SIZE));
    if (totalPages <= 1) {
      productsPagination.innerHTML = "";
      return;
    }
    var items =
      '<li class="page-item' +
      (data.previous ? "" : " disabled") +
      '"><a class="page-link js-vendor-products-page" href="#" data-page="' +
      (page - 1) +
      '"><i class="fi-rs-arrow-small-left"></i></a></li>';
    for (var i = 1; i <= totalPages; i++) {
      items +=
        '<li class="page-item' +
        (i === page ? " active" : "") +
        '"><a class="page-link js-vendor-products-page" href="#" data-page="' +
        i +
        '">' +
        i +
        "</a></li>";
    }
    items +=
      '<li class="page-item' +
      (data.next ? "" : " disabled") +
      '"><a class="page-link js-vendor-products-page" href="#" data-page="' +
      (page + 1) +
      '"><i class="fi-rs-arrow-small-right"></i></a></li>';
    productsPagination.innerHTML =
      '<nav aria-label="Page navigation example"><ul class="pagination justify-content-start">' +
      items +
      "</ul></nav>";
  }

  function loadProducts(page) {
    page = page || 1;
    Api.get("vendors/dashboard/products/", { page: page, page_size: PRODUCTS_PAGE_SIZE })
      .then(function (data) {
        var results = data.results || [];
        if (!results.length) {
          productsGrid.innerHTML =
            '<div class="col-12"><p class="mb-0">You have not added any products yet.</p></div>';
          if (productsPagination) productsPagination.innerHTML = "";
          return;
        }
        productsGrid.innerHTML = results.map(productCardHtml).join("");
        renderPagination(page, data);
      })
      .catch(function () {
        productsGrid.innerHTML =
          '<div class="col-12"><p class="mb-0">Could not load your products right now.</p></div>';
      });
  }

  if (productsPagination) {
    productsPagination.addEventListener("click", function (e) {
      var link = e.target.closest(".js-vendor-products-page");
      if (!link || link.closest(".disabled")) return;
      e.preventDefault();
      var page = parseInt(link.getAttribute("data-page"), 10);
      if (!page || page < 1) return;
      loadProducts(page);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(function () {
      loadOrders();
      loadBestSellers();
      loadProducts(1);
    });
  });
})(window, document);
