(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var itemsBody = document.querySelector(".js-checkout-items-body");
  if (!itemsBody) return;

  var SHIPPING_FLAT = 5.0;
  var FREE_SHIPPING_AT = 50.0;
  var currentCart = null;

  function rowHtml(item) {
    var p = item.product;
    return (
      "<tr><td class=\"image product-thumbnail\">" +
      (p.image ? '<img src="' + p.image + '" alt="' + Site.escapeHtml(p.name) + '">' : "") +
      '</td><td><h6 class="w-160 mb-5">' +
      Site.escapeHtml(p.name) +
      '</h6></td><td><h6 class="text-muted pl-20 pr-20">x ' +
      item.quantity +
      '</h6></td><td><h4 class="text-brand">' +
      Site.formatMoney(item.subtotal) +
      "</h4></td></tr>"
    );
  }

  function renderTotals(subtotal, discountPercent) {
    var shipping = subtotal >= FREE_SHIPPING_AT ? 0 : SHIPPING_FLAT;
    var discount = discountPercent ? (subtotal * discountPercent) / 100 : 0;
    var total = subtotal + shipping - discount;

    document.querySelector(".js-checkout-subtotal").textContent = Site.formatMoney(subtotal);
    document.querySelector(".js-checkout-shipping").textContent = shipping === 0 ? "Free" : Site.formatMoney(shipping);
    if (discount > 0) {
      document.querySelector(".js-checkout-discount-row").style.display = "";
      document.querySelector(".js-checkout-discount").textContent = "-" + Site.formatMoney(discount);
    }
    document.querySelector(".js-checkout-total").textContent = Site.formatMoney(total);
  }

  function loadCart() {
    return Api.get("cart/").then(function (cart) {
      currentCart = cart;
      document.querySelector(".js-checkout-item-count").textContent = cart.items.length;
      itemsBody.innerHTML = cart.items.map(rowHtml).join("");
      renderTotals(parseFloat(cart.subtotal), getAppliedDiscountPercent());
    });
  }

  function getAppliedDiscountPercent() {
    return parseFloat(sessionStorage.getItem("nexora_coupon_discount") || "0") || 0;
  }

  function loadAddress() {
    return Api.get("addresses/", { page_size: 1 }).then(function (data) {
      if (!data.results.length) return;
      var addr = data.results[0];
      document.getElementById("checkout-fname").value = addr.full_name.split(" ")[0] || "";
      document.getElementById("checkout-lname").value = addr.full_name.split(" ").slice(1).join(" ") || "";
      document.getElementById("checkout-address1").value = addr.address_line1 || "";
      document.getElementById("checkout-city").value = addr.city || "";
      document.getElementById("checkout-zip").value = addr.postal_code || "";
      document.getElementById("checkout-phone").value = addr.phone || "";
      document.getElementById("checkout-company").value = addr.company || "";
    });
  }

  function buildAddressPayload(prefix) {
    var fname = document.getElementById(prefix + "fname").value.trim();
    var lname = document.getElementById(prefix + "lname").value.trim();
    var countrySelect = document.getElementById(
      prefix === "checkout-" ? "checkout-country" : "checkout-ship-country"
    );
    var countryText = countrySelect && countrySelect.selectedOptions.length
      ? countrySelect.selectedOptions[0].text
      : "";
    return {
      full_name: (fname + " " + lname).trim(),
      phone: document.getElementById("checkout-phone").value.trim(),
      country: countryText || "Unknown",
      city: document.getElementById(prefix + "city").value.trim(),
      postal_code: document.getElementById(prefix + "zip").value.trim(),
      address_line1: document.getElementById(prefix + "address1").value.trim(),
      company: document.getElementById(prefix + "company") ? document.getElementById(prefix + "company").value.trim() : "",
    };
  }

  function wireCoupon() {
    var form = document.getElementById("checkout-coupon-form");
    var storedCode = sessionStorage.getItem("nexora_coupon_code");
    if (storedCode) document.getElementById("checkout-coupon-input").value = storedCode;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var code = document.getElementById("checkout-coupon-input").value.trim();
      if (!code) return;
      Api.post("coupons/validate/", { code: code }).then(function (data) {
        if (data.is_valid) {
          sessionStorage.setItem("nexora_coupon_code", code);
          sessionStorage.setItem("nexora_coupon_discount", data.discount_percent);
          Site.showToast(data.discount_percent + "% coupon applied.");
        } else {
          Site.showToast("This coupon is not valid.", "danger");
        }
        if (currentCart) renderTotals(parseFloat(currentCart.subtotal), getAppliedDiscountPercent());
      }).catch(function (err) {
        Site.showToast(err.message || "Invalid coupon.", "danger");
      });
    });
  }

  function showError(message) {
    var box = document.querySelector(".js-checkout-error");
    box.style.display = message ? "" : "none";
    box.textContent = message || "";
  }

  /**
   * "Already have an account?" and "Create an account?" are guest-only
   * affordances. Checkout requires a verified, logged-in user to reach
   * this page in the first place (see CheckoutView / the cart & order
   * APIs), so once the real auth state loads there is never a signed-in
   * visitor for whom these should show. Driven off Site.isAuthenticated()
   * (real session state), not any local/frontend flag.
   */
  function applyAuthVisibility() {
    var isAuthenticated = Site.isAuthenticated();
    var guestLogin = document.querySelector(".js-checkout-guest-login");
    var createAccount = document.querySelector(".js-checkout-create-account");
    if (guestLogin) guestLogin.style.display = isAuthenticated ? "none" : "";
    if (createAccount) createAccount.style.display = isAuthenticated ? "none" : "";
  }

  /**
   * Deterministic checkbox -> collapsible-panel wiring. Previously this
   * relied on Bootstrap's data-bs-toggle="collapse" bound to the <label>,
   * which only fires when the label TEXT is clicked -- clicking the
   * checkbox square itself changed `checked` without opening/closing the
   * panel, so the two could visibly desync. Binding directly to the
   * checkbox's `change` event keeps them in lockstep regardless of where
   * the user clicks (checkbox or label).
   */
  function wireCollapseToggles() {
    document.querySelectorAll(".js-collapse-toggle").forEach(function (label) {
      var targetId = label.getAttribute("data-collapse-target");
      var target = targetId && document.getElementById(targetId);
      var checkboxId = label.getAttribute("for");
      var checkbox = checkboxId && document.getElementById(checkboxId);
      if (!target || !checkbox) return;

      function sync() {
        target.classList.toggle("show", checkbox.checked);
      }
      checkbox.addEventListener("change", sync);
      sync();
    });
  }

  function placeOrder() {
    if (!currentCart || !currentCart.items.length) {
      showError("Your cart is empty.");
      return;
    }
    var billingPayload = buildAddressPayload("checkout-");
    if (!billingPayload.full_name || !billingPayload.address_line1 || !billingPayload.city) {
      showError("Please fill in your billing details (name, address, city).");
      return;
    }

    var shipDifferent = document.getElementById("differentaddress").checked;
    var paymentMethod = document.querySelector('input[name="payment_option"]:checked').value;
    var couponCode = sessionStorage.getItem("nexora_coupon_code") || "";

    showError("");

    Api.post("addresses/", billingPayload)
      .then(function (billingAddress) {
        if (shipDifferent) {
          var shipPayload = buildAddressPayload("checkout-ship-");
          return Api.post("addresses/", shipPayload).then(function (shipAddress) {
            return { billing: billingAddress, shipping: shipAddress };
          });
        }
        return { billing: billingAddress, shipping: billingAddress };
      })
      .then(function (addresses) {
        return Api.post("orders/", {
          shipping_address_id: addresses.shipping.id,
          billing_address_id: addresses.billing.id,
          coupon_code: couponCode,
          payment_method: paymentMethod,
        });
      })
      .then(function (order) {
        sessionStorage.removeItem("nexora_coupon_code");
        sessionStorage.removeItem("nexora_coupon_discount");
        window.location.href = "/orders/invoice/" + encodeURIComponent(order.order_number) + "/";
      })
      .catch(function (error) {
        if (error.status === 401 || error.status === 403) {
          Site.goToLogin();
          return;
        }
        showError(error.message || "Could not place order.");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireCoupon();
    wireCollapseToggles();
    document.getElementById("js-place-order").addEventListener("click", function (e) {
      e.preventDefault();
      placeOrder();
    });
    Site.ready().then(function () {
      applyAuthVisibility();
      loadCart();
      loadAddress();
    });
  });
})(window, document);
