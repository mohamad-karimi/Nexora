(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var body = document.querySelector(".js-cart-items-body");
  if (!body) return;

  // Mirrors FLAT_SHIPPING_COST / FREE_SHIPPING_THRESHOLD in
  // api/v1/serializers/orders.py (same values checkout.js previews
  // with) - shipping does not depend on destination in this project,
  // only on the cart subtotal, so this is computed client-side.
  var SHIPPING_FLAT = 5.0;
  var FREE_SHIPPING_AT = 50.0;

  var COUPON_CODE_KEY = "nexora_coupon_code";
  var COUPON_DISCOUNT_KEY = "nexora_coupon_discount";

  var currentCart = null;
  var shippingCost = null; // null = not calculated yet for this cart state
  var appliedDiscountPercent = 0;

  function round2(n) {
    return Math.round(n * 100) / 100;
  }

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

  function recomputeTotals() {
    if (!currentCart) return;

    var subtotal = parseFloat(currentCart.subtotal) || 0;
    var discountAmount = appliedDiscountPercent
      ? round2((subtotal * appliedDiscountPercent) / 100)
      : 0;
    if (discountAmount > subtotal) discountAmount = subtotal;

    var discountRows = document.querySelectorAll(".js-cart-discount-row");
    if (discountAmount > 0) {
      discountRows.forEach(function (row) {
        row.style.display = "";
      });
      var discountEl = document.querySelector(".js-cart-discount");
      if (discountEl) discountEl.textContent = "-" + Site.formatMoney(discountAmount);
    } else {
      discountRows.forEach(function (row) {
        row.style.display = "none";
      });
    }

    var shippingNote = document.querySelector(".js-cart-shipping-note");
    if (shippingNote) {
      if (shippingCost === null) {
        shippingNote.textContent = "Calculated at checkout";
      } else {
        shippingNote.textContent = shippingCost === 0 ? "Free" : Site.formatMoney(shippingCost);
      }
    }

    var total = subtotal - discountAmount + (shippingCost || 0);
    if (total < 0) total = 0;

    var subtotalEl = document.querySelector(".js-cart-subtotal");
    if (subtotalEl) subtotalEl.textContent = Site.formatMoney(subtotal);
    var totalEl = document.querySelector(".js-cart-total");
    if (totalEl) totalEl.textContent = Site.formatMoney(total);
  }

  function render(cart) {
    currentCart = cart;

    if (!cart.items.length) {
      body.innerHTML =
        '<tr><td colspan="6" class="text-center py-4">Your cart is empty. <a href="/shop/grid-left/">Continue shopping</a></td></tr>';
    } else {
      body.innerHTML = cart.items.map(rowHtml).join("");
    }

    var countEl = document.querySelector(".js-cart-item-count");
    if (countEl) countEl.textContent = cart.total_items;

    recomputeTotals();
  }

  function load() {
    return Api.get("cart/").then(render);
  }

  function removeItem(itemId) {
    return Api.delete("cart/items/" + itemId + "/")
      .then(function (cart) {
        shippingCost = null; // cart contents changed - previous quote is stale
        render(cart);
        if (Site && Site.refreshCart) Site.refreshCart();
      })
      .catch(function (err) {
        Site.showToast(err.message || "Could not remove item.", "danger");
      });
  }

  // --- Quantity +/- only adjust the input locally; "Update Cart" is
  // what actually persists the new quantities (see updateCartAll). ---
  body.addEventListener("click", function (e) {
    var row = e.target.closest("tr[data-item-id]");
    if (!row) return;

    if (e.target.closest(".js-qty-up")) {
      e.preventDefault();
      var input = row.querySelector(".js-qty-input");
      input.value = (parseInt(input.value, 10) || 1) + 1;
    } else if (e.target.closest(".js-qty-down")) {
      e.preventDefault();
      var input2 = row.querySelector(".js-qty-input");
      input2.value = Math.max(1, (parseInt(input2.value, 10) || 1) - 1);
    } else if (e.target.closest(".js-remove-item")) {
      e.preventDefault();
      removeItem(row.getAttribute("data-item-id"));
    }
  });

  // --- Clear Cart ---
  function wireClearCart() {
    var link = document.querySelector(".js-clear-cart");
    if (!link) return;
    link.addEventListener("click", function (e) {
      e.preventDefault();
      Api.delete("cart/")
        .then(function (cart) {
          shippingCost = null;
          render(cart);
          if (Site && Site.refreshCart) Site.refreshCart();
          Site.showToast("Cart cleared.");
        })
        .catch(function (err) {
          Site.showToast(err.message || "Could not clear cart.", "danger");
        });
    });
  }

  // --- Update Cart (commits every row's current quantity) ---
  function wireUpdateCart() {
    var btn = document.querySelector(".js-update-cart-btn");
    if (!btn) return;
    var msg = document.querySelector(".js-update-cart-message");

    btn.addEventListener("click", function (e) {
      e.preventDefault();
      if (!currentCart || !currentCart.items.length) return;

      var rows = body.querySelectorAll("tr[data-item-id]");
      var updates = [];
      var clampMessages = [];

      rows.forEach(function (row) {
        var input = row.querySelector(".js-qty-input");
        if (!input) return;
        var qty = parseInt(input.value, 10);
        if (!qty || qty < 1) {
          qty = 1;
          input.value = "1";
          clampMessages.push("Quantity must be at least 1.");
        }
        updates.push({ id: row.getAttribute("data-item-id"), quantity: qty });
      });

      if (!updates.length) return;

      var errors = clampMessages.slice();

      Promise.all(
        updates.map(function (u) {
          return Api.patch("cart/items/" + u.id + "/", { quantity: u.quantity }).catch(
            function (err) {
              errors.push(err.message || "Could not update an item.");
            }
          );
        })
      )
        .then(function () {
          shippingCost = null; // subtotal may have changed - re-quote needed
          return load();
        })
        .then(function () {
          if (Site && Site.refreshCart) Site.refreshCart();
          if (!msg) return;
          msg.style.display = "";
          if (errors.length) {
            msg.className = "js-update-cart-message mt-10 text-danger";
            msg.textContent = errors.join(" ");
          } else {
            msg.className = "js-update-cart-message mt-10 text-success";
            msg.textContent = "Cart updated.";
          }
        });
    });
  }

  // --- Calculate Shipping ---
  function wireShippingForm() {
    var form = document.querySelector(".js-shipping-form");
    if (!form) return;
    var msg = document.querySelector(".js-shipping-message");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!msg) return;
      msg.style.display = "none";

      if (!currentCart || !currentCart.items.length) {
        msg.style.display = "";
        msg.className = "js-shipping-message mt-10 text-danger";
        msg.textContent = "Your cart is empty - add a product before calculating shipping.";
        return;
      }

      var countryEl = document.getElementById("shipping-country");
      var stateEl = document.getElementById("shipping-state");
      var postcodeEl = document.getElementById("shipping-postcode");
      var country = countryEl ? countryEl.value.trim() : "";
      var state = stateEl ? stateEl.value.trim() : "";
      var postcode = postcodeEl ? postcodeEl.value.trim() : "";

      if (!country || !state || !postcode) {
        msg.style.display = "";
        msg.className = "js-shipping-message mt-10 text-danger";
        msg.textContent = "Please fill in country, state/province and postcode.";
        return;
      }

      var subtotal = parseFloat(currentCart.subtotal) || 0;
      shippingCost = subtotal >= FREE_SHIPPING_AT ? 0 : SHIPPING_FLAT;
      recomputeTotals();

      msg.style.display = "";
      msg.className = "js-shipping-message mt-10 text-success";
      msg.textContent =
        shippingCost === 0
          ? "You qualify for free shipping!"
          : "Shipping to " + country + ": " + Site.formatMoney(shippingCost);
    });
  }

  // --- Apply Coupon ---
  function applyCouponResult(code, discountPercent, msg) {
    appliedDiscountPercent = discountPercent;
    sessionStorage.setItem(COUPON_CODE_KEY, code);
    sessionStorage.setItem(COUPON_DISCOUNT_KEY, String(discountPercent));
    recomputeTotals();
    if (msg) {
      msg.style.display = "";
      msg.className = "js-coupon-message mt-10 text-success";
      msg.textContent = "Coupon applied - " + discountPercent + "% off.";
    }
  }

  function clearAppliedCoupon() {
    appliedDiscountPercent = 0;
    sessionStorage.removeItem(COUPON_CODE_KEY);
    sessionStorage.removeItem(COUPON_DISCOUNT_KEY);
    recomputeTotals();
  }

  function wireCouponForm() {
    var couponForm = document.getElementById("couponForm");
    if (!couponForm) return;
    var input = document.getElementById("coupon-input");
    var msg = document.querySelector(".js-coupon-message");

    var storedCode = sessionStorage.getItem(COUPON_CODE_KEY);
    if (storedCode && input) input.value = storedCode;

    couponForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var code = input.value.trim();
      if (!code) return;
      Api.post("coupons/validate/", { code: code })
        .then(function (data) {
          if (data.is_valid) {
            applyCouponResult(code, data.discount_percent, msg);
          } else {
            clearAppliedCoupon();
            msg.style.display = "";
            msg.className = "js-coupon-message mt-10 text-danger";
            msg.textContent = "This coupon is not currently valid.";
          }
        })
        .catch(function (err) {
          clearAppliedCoupon();
          msg.style.display = "";
          msg.className = "js-coupon-message mt-10 text-danger";
          msg.textContent = err.message || "Invalid coupon code.";
        });
    });
  }

  // Re-validates a coupon stored from a previous visit so the cart
  // reflects it (or drops it, if it expired/was deactivated meanwhile)
  // right after refresh - the actual discount charged is still always
  // (re)computed server-side at checkout, this is only a preview.
  function reapplyStoredCoupon() {
    var code = sessionStorage.getItem(COUPON_CODE_KEY);
    if (!code) {
      recomputeTotals();
      return;
    }
    Api.post("coupons/validate/", { code: code })
      .then(function (data) {
        if (data.is_valid) {
          applyCouponResult(code, data.discount_percent, null);
        } else {
          clearAppliedCoupon();
        }
      })
      .catch(function () {
        clearAppliedCoupon();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireClearCart();
    wireUpdateCart();
    wireShippingForm();
    wireCouponForm();

    Site.ready()
      .then(load)
      .then(reapplyStoredCoupon);
  });
})(window, document);
