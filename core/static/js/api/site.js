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

  document.addEventListener("DOMContentLoaded", function () {
    wireLogout();
    wireMiniCartRemove();
    wireSearchForms();
    loadMe();
  });

  window.Site = {
    escapeHtml: escapeHtml,
    formatMoney: formatMoney,
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
