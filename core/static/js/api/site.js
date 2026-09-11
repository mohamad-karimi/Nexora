/**
 * Sitewide behaviour shared by every page: header auth state, cart /
 * wishlist counters + mini-cart dropdown, header search, logout, and
 * a few small helpers (`window.Site`) reused by the per-page scripts.
 */
(function (window, document) {
  "use strict";

  var state = {
    user: null,
    cart: null,
    wishlistMap: {}, // product_id -> wishlist item id
  };

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value === undefined || value === null ? "" : String(value);
    return div.innerHTML;
  }

  function formatMoney(value) {
    var number = Number(value);
    if (isNaN(number)) number = 0;
    return "$" + number.toFixed(2);
  }

  function ratingWidth(avg) {
    var value = avg || 0;
    return Math.max(0, Math.min(100, (value / 5) * 100));
  }

  /**
   * Builds the standard "product-cart-wrap" grid card markup (same
   * card used on the shop listing pages) for a product returned by
   * /api/v1/products/. Shared by every page that lists products
   * (home, shop filter, compare, related products...) so they all
   * render/behave identically and stay in sync with the wishlist/cart.
   */
  function buildProductCard(product) {
    var esc = escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    var hasDiscount = product.is_on_sale;
    var wishClass = isWishlisted(product.id) ? "active" : "";
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
      '<a aria-label="Compare" class="action-btn" href="/shop/compare/?add=' +
      product.id +
      '"><i class="fi-rs-shuffle"></i></a>' +
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
      ratingWidth(product.average_rating) +
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
      formatMoney(product.final_price) +
      "</span>" +
      (hasDiscount
        ? '<span class="old-price">' + formatMoney(product.price) + "</span>"
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

  /**
   * Compact "style-2" card used by Deals-of-the-day style carousels
   * (home page + shop filter page). Only ever called with products
   * that are actually on sale (product.is_on_sale === true).
   */
  function buildDealCard(product) {
    var esc = escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    return (
      '<div class="col-xl-3 col-lg-4 col-md-6">' +
      '<div class="product-cart-wrap style-2">' +
      '<div class="product-img-action-wrap">' +
      '<div class="product-img"><a href="' +
      url +
      '">' +
      (img ? '<img src="' + img + '" alt="' + esc(product.name) + '" />' : "") +
      "</a></div></div>" +
      '<div class="product-content-wrap">' +
      '<div class="deals-content">' +
      '<h2><a href="' +
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
      ")</span></div>" +
      '<div><span class="font-small text-muted">By <a href="/shop/filter/?vendor=' +
      encodeURIComponent(product.vendor.slug) +
      '">' +
      esc(product.vendor.store_name) +
      "</a></span></div>" +
      '<div class="product-card-bottom">' +
      '<div class="product-price"><span>' +
      formatMoney(product.final_price) +
      '</span><span class="old-price">' +
      formatMoney(product.price) +
      "</span></div>" +
      '<div class="add-cart">' +
      (product.in_stock
        ? '<a class="add js-add-to-cart" href="#" data-product-id="' +
          product.id +
          '"><i class="fi-rs-shopping-cart mr-5"></i>Add </a>'
        : '<span class="add text-muted">Out of stock</span>') +
      "</div></div></div></div></div></div>"
    );
  }

  /**
   * Small "product-list-small" row used by compact widgets (home page
   * 4-column footer section, sidebar "New products").
   */
  function buildMiniCard(product) {
    var esc = escapeHtml;
    var url = "/shop/product/" + encodeURIComponent(product.slug) + "/";
    var img = product.image || "";
    return (
      '<article class="row align-items-center hover-up">' +
      '<figure class="col-md-4 mb-0"><a href="' +
      url +
      '">' +
      (img ? '<img src="' + img + '" alt="' + esc(product.name) + '" />' : "") +
      "</a></figure>" +
      '<div class="col-md-8 mb-0">' +
      "<h6><a href=\"" +
      url +
      '">' +
      esc(product.name) +
      "</a></h6>" +
      '<div class="product-rate-cover">' +
      '<div class="product-rate d-inline-block"><div class="product-rating" style="width: ' +
      ratingWidth(product.average_rating) +
      '%"></div></div>' +
      '<span class="font-small ml-5 text-muted"> (' +
      (product.average_rating ? product.average_rating.toFixed(1) : "0") +
      ")</span></div>" +
      '<div class="product-price"><span>' +
      formatMoney(product.final_price) +
      "</span>" +
      (product.is_on_sale
        ? '<span class="old-price">' + formatMoney(product.price) + "</span>"
        : "") +
      "</div></div></article>"
    );
  }

  function showToast(message, type) {
    var container = document.getElementById("js-toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "js-toast-container";
      container.style.position = "fixed";
      container.style.top = "90px";
      container.style.right = "20px";
      container.style.zIndex = "10000";
      container.style.maxWidth = "320px";
      document.body.appendChild(container);
    }
    var toast = document.createElement("div");
    toast.className = "alert alert-" + (type || "success");
    toast.style.boxShadow = "0 2px 10px rgba(0,0,0,.15)";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
      toast.style.transition = "opacity .4s";
      toast.style.opacity = "0";
      setTimeout(function () {
        toast.remove();
      }, 400);
    }, 3000);
  }

  function goToLogin() {
    window.location.href =
      "/login/?next=" + encodeURIComponent(window.location.pathname + window.location.search);
  }

  function setAllText(selector, text) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.textContent = text;
    });
  }

  function setAllDisplay(selector, visible) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.style.display = visible ? "" : "none";
    });
  }

  function renderAuthState() {
    var loggedIn = !!state.user;
    setAllDisplay(".js-auth-in", loggedIn);
    setAllDisplay(".js-auth-out", !loggedIn);
    if (loggedIn) {
      var name =
        (state.user.profile && state.user.profile.display_name) || state.user.username;
      setAllText(".js-account-label", name);
    } else {
      setAllText(".js-account-label", "Account");
    }
  }

  function renderCounts() {
    var cartCount = state.cart ? state.cart.total_items : 0;
    var wishlistCount = Object.keys(state.wishlistMap).length;
    setAllText(".js-cart-count", String(cartCount));
    setAllText(".js-wishlist-count", String(wishlistCount));
  }

  function renderMiniCart() {
    var items = (state.cart && state.cart.items) || [];
    var listHtml = "";
    if (items.length === 0) {
      listHtml = '<li class="js-mini-cart-empty">Your cart is empty.</li>';
    } else {
      items.forEach(function (item) {
        var product = item.product;
        listHtml +=
          '<li><div class="shopping-cart-img"><a href="/shop/product/' +
          encodeURIComponent(product.slug) +
          '/">' +
          (product.image
            ? '<img alt="' + escapeHtml(product.name) + '" src="' + product.image + '" />'
            : "") +
          '</a></div><div class="shopping-cart-title"><h4><a href="/shop/product/' +
          encodeURIComponent(product.slug) +
          '/">' +
          escapeHtml(product.name) +
          '</a></h4><h4><span>' +
          item.quantity +
          " × </span>" +
          formatMoney(item.unit_price) +
          '</h4></div><div class="shopping-cart-delete"><a href="#" class="js-mini-cart-remove" data-item-id="' +
          item.id +
          '"><i class="fi-rs-cross-small"></i></a></div></li>';
      });
    }
    document.querySelectorAll(".js-mini-cart-items").forEach(function (el) {
      el.innerHTML = listHtml;
    });
    setAllText(".js-mini-cart-total", formatMoney(state.cart ? state.cart.subtotal : 0));
  }

  function loadWishlist() {
    return window.Api.get("wishlist/", { page_size: 200 })
      .then(function (data) {
        state.wishlistMap = {};
        (data.results || []).forEach(function (item) {
          state.wishlistMap[item.product.id] = item.id;
        });
        renderCounts();
      })
      .catch(function () {
        state.wishlistMap = {};
      });
  }

  function loadCart() {
    return window.Api.get("cart/")
      .then(function (data) {
        state.cart = data;
        renderCounts();
        renderMiniCart();
      })
      .catch(function () {
        state.cart = null;
      });
  }

  function loadMe() {
    return window.Api.get("auth/me/")
      .then(function (data) {
        state.user = data;
        renderAuthState();
        return Promise.all([loadCart(), loadWishlist()]);
      })
      .catch(function () {
        state.user = null;
        renderAuthState();
        renderCounts();
        renderMiniCart();
      });
  }

  function addToCart(productId, quantity) {
    return window.Api.post("cart/items/", {
      product_id: productId,
      quantity: quantity || 1,
    })
      .then(function (cart) {
        state.cart = cart;
        renderCounts();
        renderMiniCart();
        showToast("Added to cart.");
        return cart;
      })
      .catch(function (error) {
        if (error.status === 401 || error.status === 403) {
          goToLogin();
        } else {
          showToast(error.message || "Could not add to cart.", "danger");
        }
        throw error;
      });
  }

  function removeCartItem(itemId) {
    return window.Api.delete("cart/items/" + itemId + "/").then(function (cart) {
      state.cart = cart;
      renderCounts();
      renderMiniCart();
      return cart;
    });
  }

  function isWishlisted(productId) {
    return Object.prototype.hasOwnProperty.call(state.wishlistMap, productId);
  }

  function toggleWishlist(productId) {
    if (!state.user) {
      goToLogin();
      return Promise.reject(new Error("Not authenticated"));
    }
    if (isWishlisted(productId)) {
      var itemId = state.wishlistMap[productId];
      return window.Api.delete("wishlist/" + itemId + "/").then(function () {
        delete state.wishlistMap[productId];
        renderCounts();
        showToast("Removed from wishlist.");
        return false;
      });
    }
    return window.Api.post("wishlist/", { product_id: productId }).then(function (item) {
      state.wishlistMap[productId] = item.id;
      renderCounts();
      showToast("Added to wishlist.");
      return true;
    });
  }

  function wireLogout() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest(".js-logout-link");
      if (!link) return;
      event.preventDefault();
      window.Api.post("auth/logout/").finally(function () {
        window.location.href = "/";
      });
    });
  }

  function wireMiniCartRemove() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest(".js-mini-cart-remove");
      if (!link) return;
      event.preventDefault();
      removeCartItem(link.getAttribute("data-item-id"));
    });
  }

  function wireSearchForms() {
    document.querySelectorAll(".js-search-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var input = form.querySelector(".js-search-input");
        var query = input ? input.value.trim() : "";
        var url = form.getAttribute("action") || "/shop/grid-left/";
        window.location.href = query ? url + "?q=" + encodeURIComponent(query) : url;
      });
    });
  }

  /**
   * Sitewide delegated handling for the two product-card actions that
   * appear on many pages (home, shop listing/filter, compare, related
   * products, wishlist...): wishlist toggle and add-to-cart. Any markup
   * anywhere on the site can opt in just by using these classes/data
   * attributes - no per-page wiring required.
   */
  function wireProductActions() {
    document.addEventListener("click", function (event) {
      var wishlistBtn = event.target.closest(".js-wishlist-toggle");
      if (wishlistBtn) {
        event.preventDefault();
        var productId = parseInt(wishlistBtn.getAttribute("data-product-id"), 10);
        toggleWishlist(productId).then(function () {
          document
            .querySelectorAll('.js-wishlist-toggle[data-product-id="' + productId + '"]')
            .forEach(function (btn) {
              btn.classList.toggle("active", isWishlisted(productId));
            });
        });
        return;
      }

      var addToCartBtn = event.target.closest(".js-add-to-cart");
      if (addToCartBtn) {
        event.preventDefault();
        var pid = parseInt(addToCartBtn.getAttribute("data-product-id"), 10);
        var qty = parseInt(addToCartBtn.getAttribute("data-quantity"), 10) || 1;
        addToCart(pid, qty);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireLogout();
    wireMiniCartRemove();
    wireSearchForms();
    wireProductActions();
    loadMe();
  });

  window.Site = {
    escapeHtml: escapeHtml,
    formatMoney: formatMoney,
    ratingWidth: ratingWidth,
    buildProductCard: buildProductCard,
    buildDealCard: buildDealCard,
    buildMiniCard: buildMiniCard,
    showToast: showToast,
    goToLogin: goToLogin,
    addToCart: addToCart,
    removeCartItem: removeCartItem,
    toggleWishlist: toggleWishlist,
    isWishlisted: isWishlisted,
    refreshCart: loadCart,
    refreshWishlist: loadWishlist,
    getUser: function () {
      return state.user;
    },
    isAuthenticated: function () {
      return !!state.user;
    },
    ready: loadMe,
  };
})(window, document);
