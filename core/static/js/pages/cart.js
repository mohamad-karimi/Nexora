(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var body = document.querySelector(".js-cart-items-body");
  if (!body) return;

  function rowHtml(item) {
    var esc = Site.escapeHtml;
    var p = item.product;
    var url = "/shop/product/" + encodeURIComponent(p.slug) + "/";
    return (
      '<tr data-item-id="' +
      item.id +
      '"><td class="custome-checkbox pl-30"></td><td class="image product-thumbnail"><img src="' +
      (p.image || "") +
      '" alt="' +
      esc(p.name) +
      '"></td><td class="product-des product-name"><h6 class="mb-5"><a class="product-name mb-10 text-heading" href="' +
      url +
      '">' +
      esc(p.name) +
      '</a></h6></td><td class="price" data-title="Price"><h4 class="text-body">' +
      Site.formatMoney(item.unit_price) +
      '</h4></td><td class="text-center detail-info" data-title="Qty"><div class="detail-extralink mr-15"><div class="detail-qty border radius"><a href="#" class="qty-down js-qty-down"><i class="fi-rs-angle-small-down"></i></a><input type="text" class="qty-val js-qty-input" value="' +
      item.quantity +
      '" min="1"><a href="#" class="qty-up js-qty-up"><i class="fi-rs-angle-small-up"></i></a></div></div></td><td class="price" data-title="Subtotal"><h4 class="text-brand js-row-subtotal">' +
      Site.formatMoney(item.subtotal) +
      '</h4></td><td class="action text-center" data-title="Remove"><a href="#" class="text-body js-remove-item"><i class="fi-rs-trash"></i></a></td></tr>'
    );
  }

  function render(cart) {
    if (!cart.items.length) {
      body.innerHTML =
        '<tr><td colspan="6" class="text-center py-4">Your cart is empty. <a href="/shop/grid-left/">Continue shopping</a></td></tr>';
    } else {
      body.innerHTML = cart.items.map(rowHtml).join("");
    }
    document.querySelector(".js-cart-subtotal").textContent = Site.formatMoney(cart.subtotal);
    document.querySelector(".js-cart-total").textContent = Site.formatMoney(cart.subtotal);
  }

  function load() {
    return Api.get("cart/").then(render);
  }

  function updateQty(itemId, quantity) {
    return Api.patch("cart/items/" + itemId + "/", { quantity: quantity }).then(render);
  }

  function removeItem(itemId) {
    return Api.delete("cart/items/" + itemId + "/").then(render);
  }

  body.addEventListener("click", function (e) {
    var row = e.target.closest("tr[data-item-id]");
    if (!row) return;
    var itemId = row.getAttribute("data-item-id");

    if (e.target.closest(".js-qty-up")) {
      e.preventDefault();
      var input = row.querySelector(".js-qty-input");
      updateQty(itemId, (parseInt(input.value, 10) || 1) + 1);
    } else if (e.target.closest(".js-qty-down")) {
      e.preventDefault();
      var input2 = row.querySelector(".js-qty-input");
      var next = Math.max(1, (parseInt(input2.value, 10) || 1) - 1);
      updateQty(itemId, next);
    } else if (e.target.closest(".js-remove-item")) {
      e.preventDefault();
      removeItem(itemId);
    }
  });

  var couponForm = document.getElementById("couponForm");
  if (couponForm) {
    couponForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var code = document.getElementById("coupon-input").value.trim();
      var msg = document.querySelector(".js-coupon-message");
      if (!code) return;
      Api.post("coupons/validate/", { code: code })
        .then(function (data) {
          if (data.is_valid) {
            window.sessionStorage.setItem("nexora_coupon_code", code);
            msg.style.display = "";
            msg.className = "js-coupon-message mt-10 text-success";
            msg.textContent = "Coupon applied - " + data.discount_percent + "% off will be applied at checkout.";
          } else {
            msg.style.display = "";
            msg.className = "js-coupon-message mt-10 text-danger";
            msg.textContent = "This coupon is not currently valid.";
          }
        })
        .catch(function (err) {
          msg.style.display = "";
          msg.className = "js-coupon-message mt-10 text-danger";
          msg.textContent = err.message || "Invalid coupon code.";
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(load);
  });
})(window, document);
