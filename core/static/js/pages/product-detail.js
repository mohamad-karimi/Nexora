(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var root = document.getElementById("js-product-detail");
  if (!root) return;
  var slug = root.getAttribute("data-product-slug");
  var currentProduct = null;

  // ---------------------------------------------------------------------
  // Safe DOM helpers
  //
  // Every page section below is only ever touched through these helpers
  // (or through qs()/qsa() directly). They never throw just because an
  // element is missing - they simply no-op - so a template change or a
  // partially-rendered section can't turn into an unhandled exception
  // that takes the rest of the page down with it.
  // ---------------------------------------------------------------------
  function qs(selector, ctx) {
    return (ctx || document).querySelector(selector);
  }

  function qsa(selector, ctx) {
    return Array.prototype.slice.call((ctx || document).querySelectorAll(selector));
  }

  function setText(selector, value) {
    var el = qs(selector);
    if (el) el.textContent = value;
    return el;
  }

  function setHtml(selector, html) {
    var el = qs(selector);
    if (el) el.innerHTML = html;
    return el;
  }

  function setDisplay(selector, display) {
    var el = qs(selector);
    if (el) el.style.display = display;
    return el;
  }

  // ---------------------------------------------------------------------
  // Section runner
  //
  // This is the core of the fix: each page section (gallery, buy box,
  // specs, vendor, reviews, related products, ...) is executed through
  // runSection(). A thrown error - synchronous or from a rejected
  // promise - is caught right here, logged to the console, and stops
  // *only* that section. It never reaches a shared/global catch, so it
  // can never wipe out root.innerHTML or any other section of the page.
  // ---------------------------------------------------------------------
  function runSection(label, fn) {
    try {
      var result = fn();
      if (result && typeof result.catch === "function") {
        result.catch(function (err) {
          logSectionError(label, err);
        });
      }
      return result;
    } catch (err) {
      logSectionError(label, err);
      return null;
    }
  }

  function logSectionError(label, err) {
    if (window.console && console.error) {
      console.error("[product-detail] " + label + " section failed:", err);
    }
  }

  function buildGalleryImages(product) {
    // Product.image (the single main image) plus every real
    // ProductImage gallery row - that's the full real image set for
    // this product, in the same order the API returns them.
    var images = [];
    if (product.image) {
      images.push({ src: product.image, alt: product.name });
    }
    (product.images || []).forEach(function (img) {
      if (img.image) {
        images.push({ src: img.image, alt: img.alt_text || product.name });
      }
    });
    return images;
  }

  function fillGallery(product) {
    var esc = Site.escapeHtml;
    var images = buildGalleryImages(product);
    var gallery = qs(".js-gallery");
    var mainEl = qs(".js-gallery-main");
    var thumbsEl = qs(".js-gallery-thumbs");
    if (!mainEl || !thumbsEl) return;

    if (!images.length) {
      // No real image at all - leave both empty rather than showing
      // any placeholder/demo picture. The bordered gallery box still
      // renders fine empty, nothing breaks.
      mainEl.innerHTML = "";
      thumbsEl.innerHTML = "";
      thumbsEl.style.display = "none";
      return;
    }

    // Exactly the markup the theme ships with - figure.border-radius-10
    // for the main slides, a plain <div> wrapper per thumbnail - so the
    // Nest gallery CSS applies unchanged.
    mainEl.innerHTML = images
      .map(function (img) {
        return (
          '<figure class="border-radius-10"><img class="js-gallery-main-img" src="' +
          esc(img.src) +
          '" alt="' +
          esc(img.alt) +
          '"></figure>'
        );
      })
      .join("");

    if (images.length > 1) {
      thumbsEl.style.display = "";
      thumbsEl.innerHTML = images
        .map(function (img) {
          return (
            '<div><img class="js-gallery-thumb-img" src="' +
            esc(img.src) +
            '" alt="' +
            esc(img.alt) +
            '"></div>'
          );
        })
        .join("");
    } else {
      // Single real image - just show it, no redundant one-thumbnail row.
      thumbsEl.innerHTML = "";
      thumbsEl.style.display = "none";
    }

    // The slides exist now, so the theme's own gallery initializer can
    // run against them. Order matters: fetch -> build markup -> insert
    // -> initialize. Initializing earlier (which is what shop.js used to
    // do at document.ready, on the still-empty containers) leaves
    // .slick-initialized behind and makes this init a no-op.
    if (window.NestGallery && typeof window.NestGallery.init === "function") {
      window.NestGallery.init(gallery || mainEl.parentNode);
    }
  }

  function fillBuyBox(product) {
    var esc = Site.escapeHtml;
    qsa(".js-product-title").forEach(function (el) {
      el.textContent = product.name;
    });
    setText(".js-breadcrumb-title", product.name);
    var catLink = qs(".js-breadcrumb-category");
    if (catLink) {
      catLink.textContent = product.category.name;
      catLink.href = "/shop/grid-left/?category=" + encodeURIComponent(product.category.slug);
    }

    if (product.is_on_sale) {
      setDisplay(".js-sale-badge", "");
    }

    setText(".js-current-price", Site.formatMoney(product.final_price));
    if (product.is_on_sale) {
      setDisplay(".js-sale-price-wrap", "");
      setText(".js-save-price", product.discount_percent + "% Off");
      setText(".js-old-price", Site.formatMoney(product.price));
    }

    setText(".js-short-description", product.short_description || "");

    var ratingEl = qs(".js-detail-rating");
    var avg = product.average_rating || 0;
    if (ratingEl) ratingEl.style.width = Math.max(0, Math.min(100, (avg / 5) * 100)) + "%";
    setText(
      ".js-detail-review-count",
      " (" + product.review_count + " review" + (product.review_count === 1 ? "" : "s") + ")"
    );

    if (product.product_type) {
      setDisplay(".js-type-row", "");
      setText(".js-product-type", product.product_type);
    }
    if (product.manufacture_date) {
      setDisplay(".js-mfg-row", "");
      setText(".js-mfg", product.manufacture_date);
    }
    if (product.shelf_life_days) {
      setDisplay(".js-life-row", "");
      setText(".js-life", product.shelf_life_days + " days");
    }
    setText(".js-sku", product.sku);
    setHtml(
      ".js-detail-tags",
      (product.tags || [])
        .map(function (t) {
          return '<a href="/shop/grid-left/?tag=' + encodeURIComponent(t.slug) + '" rel="tag">' + esc(t.name) + "</a>";
        })
        .join(", ") || "-"
    );
    var stockEl = qs(".js-stock-text");
    if (stockEl) {
      stockEl.textContent = product.in_stock ? product.stock + " Items In Stock" : "Out of Stock";
      stockEl.classList.toggle("text-brand", product.in_stock);
      stockEl.classList.toggle("text-danger", !product.in_stock);
    }

    var addBtn = qs(".js-detail-add-to-cart");
    if (addBtn && !product.in_stock) {
      addBtn.disabled = true;
      addBtn.textContent = "Out of stock";
    }

    var wishBtn = qs(".js-detail-wishlist-toggle");
    if (wishBtn && Site.isWishlisted(product.id)) wishBtn.classList.add("active");

    setHtml(
      ".js-full-description",
      "<p>" + esc(product.description || product.short_description || "").replace(/\n/g, "</p><p>") + "</p>"
    );
  }

  function fillSpecs(product) {
    var tbody = qs(".js-specs-table-body");
    var specs = product.specifications || [];
    if (!specs.length) {
      setDisplay(".js-specs-empty", "");
      return;
    }
    if (!tbody) return;
    tbody.innerHTML = specs
      .map(function (s) {
        return "<tr><th>" + Site.escapeHtml(s.name) + "</th><td><p>" + Site.escapeHtml(s.value) + "</p></td></tr>";
      })
      .join("");
  }

  function fillVendor(product) {
    var v = product.vendor;
    setText(".js-vendor-name", v.store_name);
    var vendorLink = qs(".js-vendor-link");
    if (vendorLink) vendorLink.href = "/shop/grid-left/?vendor=" + encodeURIComponent(v.slug);
    var logoEl = qs(".js-vendor-logo");
    if (v.logo && logoEl) logoEl.src = v.logo;

    // The extra vendor details (address/phone/description/product count)
    // come from a second request. If it fails, the vendor name/logo/link
    // above stay filled in - only this follow-up piece is affected.
    return Api.get("vendors/" + v.slug + "/").then(function (full) {
      setText(".js-vendor-product-count", full.product_count + " products");
      setText(".js-vendor-address", full.address || "-");
      setText(".js-vendor-phone", full.phone || "-");
      setText(".js-vendor-description", full.description || "");
    });
  }

  function renderReviews(data) {
    var esc = Site.escapeHtml;
    qsa(".js-reviews-tab-count").forEach(function (el) {
      el.textContent = data.count;
    });
    var list = qs(".js-reviews-list");
    if (list) {
      if (!data.results.length) {
        list.innerHTML = "<p>No reviews yet. Be the first to review this product.</p>";
      } else {
        list.innerHTML = data.results
          .map(function (r) {
            return (
              '<div class="single-comment justify-content-between d-flex mb-30"><div class="user justify-content-between d-flex"><div class="desc"><div class="d-flex justify-content-between mb-10"><div class="d-flex align-items-center"><strong class="mr-10">' +
              esc(r.user_display_name) +
              '</strong><span class="font-xs text-muted">' +
              new Date(r.created_date).toLocaleDateString() +
              '</span></div><div class="product-rate d-inline-block"><div class="product-rating" style="width: ' +
              (r.score / 5) * 100 +
              '%"></div></div></div><p class="mb-10">' +
              esc(r.comment) +
              (r.is_approved ? "" : ' <em class="text-muted">(pending approval)</em>') +
              "</p></div></div></div>"
            );
          })
          .join("");
      }
    }

    var sum = 0;
    var counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    data.results.forEach(function (r) {
      sum += r.score;
      counts[r.score] = (counts[r.score] || 0) + 1;
    });
    var total = data.results.length;
    if (total) {
      var avg = sum / total;
      var summaryRatingEl = qs(".js-summary-rating");
      if (summaryRatingEl) summaryRatingEl.style.width = (avg / 5) * 100 + "%";
      setText(".js-summary-rating-text", avg.toFixed(1) + " out of 5");
      var html = "";
      [5, 4, 3, 2, 1].forEach(function (star) {
        var pct = Math.round(((counts[star] || 0) / total) * 100);
        html +=
          '<div class="progress"><span>' +
          star +
          ' star</span><div class="progress-bar" role="progressbar" style="width: ' +
          pct +
          '%">' +
          pct +
          "%</div></div>";
      });
      setHtml(".js-rating-breakdown", html);
    }
  }

  function loadReviews() {
    return Api.get("products/" + slug + "/reviews/").then(renderReviews);
  }

  function wireActions() {
    var qtyDown = qs(".js-qty-down");
    if (qtyDown) {
      qtyDown.addEventListener("click", function (e) {
        e.preventDefault();
        var input = qs(".js-qty-input");
        if (input) input.value = Math.max(1, (parseInt(input.value, 10) || 1) - 1);
      });
    }
    var qtyUp = qs(".js-qty-up");
    if (qtyUp) {
      qtyUp.addEventListener("click", function (e) {
        e.preventDefault();
        var input = qs(".js-qty-input");
        if (input) input.value = (parseInt(input.value, 10) || 1) + 1;
      });
    }
    var addToCartBtn = qs(".js-detail-add-to-cart");
    if (addToCartBtn) {
      addToCartBtn.addEventListener("click", function (e) {
        e.preventDefault();
        if (!currentProduct) return;
        var btn = e.currentTarget;
        var input = qs(".js-qty-input");
        var qty = parseInt(input ? input.value : "1", 10) || 1;
        btn.disabled = true;
        Site.addToCart(currentProduct.id, qty).finally(function () {
          btn.disabled = false;
        });
      });
    }
    var wishlistBtn = qs(".js-detail-wishlist-toggle");
    if (wishlistBtn) {
      wishlistBtn.addEventListener("click", function (e) {
        e.preventDefault();
        if (!currentProduct) return;
        Site.toggleWishlist(currentProduct.id).then(function () {
          var target = e.target.closest(".js-detail-wishlist-toggle");
          if (target) target.classList.toggle("active", Site.isWishlisted(currentProduct.id));
        });
      });
    }

    var form = document.getElementById("reviewForm");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!Site.isAuthenticated()) {
          Site.goToLogin();
          return;
        }
        var scoreEl = document.getElementById("review-score");
        var commentEl = document.getElementById("review-comment");
        var score = parseInt(scoreEl ? scoreEl.value : "0", 10);
        var comment = commentEl ? commentEl.value.trim() : "";
        var msgBox = qs(".js-review-form-message");
        Api.post("products/" + slug + "/reviews/", { score: score, comment: comment })
          .then(function () {
            if (msgBox) {
              msgBox.style.display = "";
              msgBox.classList.remove("text-danger");
              msgBox.classList.add("text-success");
              msgBox.textContent = "Thanks! Your review was submitted and is pending approval.";
            }
            if (commentEl) commentEl.value = "";
            runSection("reviews", loadReviews);
          })
          .catch(function (err) {
            if (msgBox) {
              msgBox.style.display = "";
              msgBox.classList.add("text-danger");
              msgBox.textContent = err.message || "Could not submit review.";
            }
          });
      });
    }
  }

  function loadRelatedProducts(product) {
    var container = qs(".js-related-products");
    if (!container) return;
    return Api.get("products/", { category: product.category.slug, page_size: 8 })
      .then(function (data) {
        var related = data.results
          .filter(function (p) {
            return p.id !== product.id;
          })
          .slice(0, 4);
        container.innerHTML = related.length
          ? related.map(Site.buildProductCard).join("")
          : '<div class="col-12 text-center"><p class="text-muted mb-0">No related products found.</p></div>';
      })
      .catch(function (err) {
        container.innerHTML = "";
        logSectionError("related products", err);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    runSection("actions", wireActions);
    Site.ready().then(function () {
      runSection("review form auth state", function () {
        if (!Site.isAuthenticated()) {
          setDisplay(".js-review-form-wrap", "none");
          setDisplay(".js-review-login-prompt", "");
        }
      });

      // Only the primary product fetch is allowed to put the whole page
      // into an error state (product missing / request failed). Once we
      // have the product, every section below runs independently through
      // runSection(): a failure in Vendor, Reviews, Related Products,
      // Specs or the Gallery is caught, logged, and left at that - it can
      // never clear out or reset any other part of the page.
      Api.get("products/" + slug + "/")
        .then(function (product) {
          currentProduct = product;
          runSection("gallery", function () {
            fillGallery(product);
          });
          runSection("buy box", function () {
            fillBuyBox(product);
          });
          runSection("specs", function () {
            fillSpecs(product);
          });
          runSection("vendor", function () {
            return fillVendor(product);
          });
          runSection("related products", function () {
            return loadRelatedProducts(product);
          });
          runSection("reviews", loadReviews);
        })
        .catch(function (error) {
          root.innerHTML =
            '<div class="text-center py-5"><p>' +
            Site.escapeHtml(error.message || "Product not found.") +
            "</p></div>";
        });
    });
  });
})(window, document);
