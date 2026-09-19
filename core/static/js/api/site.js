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
        var categorySelect = form.querySelector(".js-header-category-select");
        var category = categorySelect ? categorySelect.value : "";
        var url = form.getAttribute("action") || "/shop/grid-left/";
        var params = [];
        if (query) params.push("q=" + encodeURIComponent(query));
        if (category) params.push("category=" + encodeURIComponent(category));
        window.location.href = params.length ? url + "?" + params.join("&") : url;
      });
    });
  }

  /**
   * Fallback icons for categories that don't have an image uploaded
   * yet, cycled by position so the "Browse All Categories" dropdown
   * keeps the same visual rhythm as the original static markup.
   */
  var HEADER_CATEGORY_FALLBACK_ICONS = [
    "category-1.svg",
    "category-2.svg",
    "category-3.svg",
    "category-4.svg",
    "category-5.svg",
    "category-6.svg",
    "category-7.svg",
    "category-8.svg",
    "category-9.svg",
    "category-10.svg",
  ];

  function categoryIconUrl(category, index) {
    if (category.image) return category.image;
    var name = HEADER_CATEGORY_FALLBACK_ICONS[index % HEADER_CATEGORY_FALLBACK_ICONS.length];
    return "/static/imgs/theme/icons/" + name;
  }

  function categoryListItemHtml(category, index) {
    var esc = escapeHtml;
    return (
      "<li><a href=\"/shop/filter/?category=" +
      encodeURIComponent(category.slug) +
      "\"> <img src=\"" +
      categoryIconUrl(category, index) +
      "\" alt=\"\" />" +
      esc(category.name) +
      "</a></li>"
    );
  }

  /**
   * Populates the "Browse All Categories" mega-dropdown and the
   * category <select> next to the header Search box from real
   * category data (/api/v1/categories/), replacing the old hardcoded
   * demo markup. Keeps the original two-column-plus-"show more"
   * layout: first 10 categories split 5/5 across the two visible
   * columns, anything beyond that goes in the collapsible
   * "more_slide_open" panel (split evenly across its two columns),
   * and the "Show more..." toggle only appears when there is
   * something to show.
   */
  function loadHeaderCategories() {
    var hasDropdown = document.querySelector(".js-header-categories-col-1");
    var selects = document.querySelectorAll(".js-header-category-select");
    if (!hasDropdown && selects.length === 0) return;

    window.Api.get("categories/", { page_size: 200, ordering: "name" })
      .then(function (data) {
        var categories = data.results || [];

        selects.forEach(function (select) {
          var optionsHtml = '<option value="">All Categories</option>';
          categories.forEach(function (category) {
            optionsHtml +=
              '<option value="' +
              escapeHtml(category.slug) +
              '">' +
              escapeHtml(category.name) +
              "</option>";
          });
          select.innerHTML = optionsHtml;
        });

        if (!hasDropdown) return;

        var visible = categories.slice(0, 10);
        var overflow = categories.slice(10);

        var col1 = document.querySelector(".js-header-categories-col-1");
        var col2 = document.querySelector(".js-header-categories-col-2");
        var splitPoint = Math.ceil(visible.length / 2);
        if (col1) {
          col1.innerHTML = visible
            .slice(0, splitPoint)
            .map(function (category, index) {
              return categoryListItemHtml(category, index);
            })
            .join("");
        }
        if (col2) {
          col2.innerHTML = visible
            .slice(splitPoint)
            .map(function (category, index) {
              return categoryListItemHtml(category, splitPoint + index);
            })
            .join("");
        }

        var moreCol1 = document.querySelector(".js-header-categories-more-col-1");
        var moreCol2 = document.querySelector(".js-header-categories-more-col-2");
        var moreSplit = Math.ceil(overflow.length / 2);
        if (moreCol1) {
          moreCol1.innerHTML = overflow
            .slice(0, moreSplit)
            .map(function (category, index) {
              return categoryListItemHtml(category, index);
            })
            .join("");
        }
        if (moreCol2) {
          moreCol2.innerHTML = overflow
            .slice(moreSplit)
            .map(function (category, index) {
              return categoryListItemHtml(category, moreSplit + index);
            })
            .join("");
        }

        var toggle = document.querySelector(".js-header-categories-toggle");
        if (toggle) {
          toggle.style.display = overflow.length ? "" : "none";
        }
      })
      .catch(function () {
        // Leave the dropdown/select empty rather than showing stale
        // demo data if the API call fails.
      });
  }

  /**
   * Populates the desktop "Mega menu" columns and the mobile Mega
   * menu accordion from real category data (/api/v1/categories/),
   * replacing the old hardcoded demo categories/links. Only real
   * top-level categories are shown (as many as there are slots, up
   * to 3); a category's real children (if any) become its
   * sub-menu. A category with no children renders as a plain link
   * (mobile: its now-pointless expand arrow + empty dropdown are
   * removed). Unused slots are hidden rather than left showing
   * stale/fake content.
   */
  function megaMenuLinkHtml(slug) {
    return "/shop/filter/?category=" + encodeURIComponent(slug);
  }

  function loadMegaMenu() {
    var desktopSlots = document.querySelectorAll(".js-mega-menu-slot");
    var mobileSlots = document.querySelectorAll(".js-mega-menu-mobile-slot");
    if (!desktopSlots.length && !mobileSlots.length) return;

    window.Api.get("categories/", { page_size: 200, ordering: "name" })
      .then(function (data) {
        var categories = data.results || [];
        var childrenByParent = {};
        categories.forEach(function (category) {
          if (category.parent) {
            childrenByParent[category.parent] = childrenByParent[category.parent] || [];
            childrenByParent[category.parent].push(category);
          }
        });
        var topLevel = categories.filter(function (category) {
          return !category.parent;
        });
        var slotCount = Math.max(desktopSlots.length, mobileSlots.length) || 3;
        var featured = topLevel.slice(0, slotCount);

        desktopSlots.forEach(function (slot, index) {
          var category = featured[index];
          if (!category) {
            slot.style.display = "none";
            slot.innerHTML = "";
            return;
          }
          var children = childrenByParent[category.id] || [];
          var titleHtml =
            '<a class="menu-title" href="' +
            megaMenuLinkHtml(category.slug) +
            '">' +
            escapeHtml(category.name) +
            "</a>";
          var childrenHtml = children.length
            ? "<ul>" +
              children
                .map(function (child) {
                  return (
                    '<li><a href="' +
                    megaMenuLinkHtml(child.slug) +
                    '">' +
                    escapeHtml(child.name) +
                    "</a></li>"
                  );
                })
                .join("") +
              "</ul>"
            : "";
          slot.innerHTML = titleHtml + childrenHtml;
          slot.style.display = "";
        });

        mobileSlots.forEach(function (slot, index) {
          var category = featured[index];
          if (!category) {
            slot.style.display = "none";
            return;
          }
          var link = slot.querySelector(".js-mega-menu-mobile-link");
          var childrenUl = slot.querySelector(".js-mega-menu-mobile-children");
          var children = childrenByParent[category.id] || [];
          if (link) {
            link.textContent = category.name;
            link.setAttribute("href", megaMenuLinkHtml(category.slug));
          }
          if (childrenUl) {
            if (children.length) {
              childrenUl.innerHTML = children
                .map(function (child) {
                  return (
                    '<li><a href="' +
                    megaMenuLinkHtml(child.slug) +
                    '">' +
                    escapeHtml(child.name) +
                    "</a></li>"
                  );
                })
                .join("");
            } else {
              // No real subcategories: drop the now-pointless expand
              // control and empty dropdown so this becomes a plain link.
              var expand = slot.querySelector(".menu-expand");
              if (expand) expand.remove();
              childrenUl.remove();
            }
          }
          slot.style.display = "";
        });
      })
      .catch(function () {
        desktopSlots.forEach(function (slot) {
          slot.style.display = "none";
        });
        mobileSlots.forEach(function (slot) {
          slot.style.display = "none";
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
    loadHeaderCategories();
    loadMegaMenu();
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
