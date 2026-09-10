(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;
  var body = document.querySelector(".js-wishlist-body");
  if (!body) return;

  function rowHtml(item) {
    var esc = Site.escapeHtml;
    var p = item.product;
    var url = "/shop/product/" + encodeURIComponent(p.slug) + "/";
    return (
      '<tr data-wishlist-id="' +
      item.id +
      '" data-product-id="' +
      p.id +
      '"><td class="custome-checkbox pl-30"></td><td class="image product-thumbnail"><img src="' +
      (p.image || "") +
      '" alt="' +
      esc(p.name) +
      '" /></td><td class="product-des product-name"><h6><a class="product-name mb-10" href="' +
      url +
      '">' +
      esc(p.name) +
      '</a></h6></td><td class="price" data-title="Price"><h3 class="text-brand">' +
      Site.formatMoney(p.final_price) +
      '</h3></td><td class="text-center detail-info" data-title="Stock"><span class="stock-status ' +
      (p.in_stock ? "in-stock" : "out-stock") +
      ' mb-0"> ' +
      (p.in_stock ? "In Stock" : "Out of stock") +
      ' </span></td><td class="text-right" data-title="Cart"><button class="btn btn-sm js-move-to-cart" ' +
      (p.in_stock ? "" : "disabled") +
      '>Add to cart</button></td><td class="action text-center" data-title="Remove"><a href="#" class="text-body js-remove-wishlist"><i class="fi-rs-trash"></i></a></td></tr>'
    );
  }

  function load() {
    return Api.get("wishlist/", { page_size: 100 }).then(function (data) {
      if (!data.results.length) {
        body.innerHTML =
          '<tr><td colspan="7" class="text-center py-4">Your wishlist is empty. <a href="/shop/grid-left/">Browse products</a></td></tr>';
        return;
      }
      body.innerHTML = data.results.map(rowHtml).join("");
    });
  }

  body.addEventListener("click", function (e) {
    var row = e.target.closest("tr[data-wishlist-id]");
    if (!row) return;
    var wishlistId = row.getAttribute("data-wishlist-id");
    var productId = parseInt(row.getAttribute("data-product-id"), 10);

    if (e.target.closest(".js-remove-wishlist")) {
      e.preventDefault();
      Api.delete("wishlist/" + wishlistId + "/").then(function () {
        Site.refreshWishlist();
        load();
      });
    } else if (e.target.closest(".js-move-to-cart")) {
      e.preventDefault();
      Site.addToCart(productId, 1);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(load);
  });
})(window, document);
