(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var root = document.getElementById("js-product-detail");
  if (!root) return;
  var slug = root.getAttribute("data-product-slug");
  var currentProduct = null;

  function fillGallery(product) {
    var images = [];
    if (product.image) images.push(product.image);
    (product.images || []).forEach(function (img) {
      images.push(img.image);
    });
    if (!images.length) images = [""];

    var mains = document.querySelectorAll(".js-gallery-main-img");
    var thumbs = document.querySelectorAll(".js-gallery-thumb-img");
    mains.forEach(function (img, i) {
      if (images[i % images.length]) img.src = images[i % images.length];
      img.alt = product.name;
    });
    thumbs.forEach(function (img, i) {
      if (images[i % images.length]) img.src = images[i % images.length];
      img.alt = product.name;
    });
  }

  function fillBuyBox(product) {
    var esc = Site.escapeHtml;
    document.querySelectorAll(".js-product-title").forEach(function (el) {
      el.textContent = product.name;
    });
    document.querySelector(".js-breadcrumb-title").textContent = product.name;
    var catLink = document.querySelector(".js-breadcrumb-category");
    catLink.textContent = product.category.name;
    catLink.href = "/shop/grid-left/?category=" + encodeURIComponent(product.category.slug);

    var saleBadge = document.querySelector(".js-sale-badge");
    if (product.is_on_sale) {
      saleBadge.style.display = "";
    }

    document.querySelector(".js-current-price").textContent = Site.formatMoney(product.final_price);
    if (product.is_on_sale) {
      document.querySelector(".js-sale-price-wrap").style.display = "";
      document.querySelector(".js-save-price").textContent = product.discount_percent + "% Off";
      document.querySelector(".js-old-price").textContent = Site.formatMoney(product.price);
    }

    document.querySelector(".js-short-description").textContent = product.short_description || "";

    var ratingEl = document.querySelector(".js-detail-rating");
    var avg = product.average_rating || 0;
    ratingEl.style.width = Math.max(0, Math.min(100, (avg / 5) * 100)) + "%";
    document.querySelector(".js-detail-review-count").textContent =
      " (" + product.review_count + " review" + (product.review_count === 1 ? "" : "s") + ")";

    if (product.product_type) {
      document.querySelector(".js-type-row").style.display = "";
      document.querySelector(".js-product-type").textContent = product.product_type;
    }
    if (product.manufacture_date) {
      document.querySelector(".js-mfg-row").style.display = "";
      document.querySelector(".js-mfg").textContent = product.manufacture_date;
    }
    if (product.shelf_life_days) {
      document.querySelector(".js-life-row").style.display = "";
      document.querySelector(".js-life").textContent = product.shelf_life_days + " days";
    }
    document.querySelector(".js-sku").textContent = product.sku;
    var tagsEl = document.querySelector(".js-detail-tags");
    tagsEl.innerHTML = (product.tags || [])
      .map(function (t) {
        return '<a href="/shop/grid-left/?tag=' + encodeURIComponent(t.slug) + '" rel="tag">' + esc(t.name) + "</a>";
      })
      .join(", ") || "-";
    var stockEl = document.querySelector(".js-stock-text");
    stockEl.textContent = product.in_stock ? product.stock + " Items In Stock" : "Out of stock";

    var addBtn = document.querySelector(".js-detail-add-to-cart");
    if (!product.in_stock) {
      addBtn.disabled = true;
      addBtn.textContent = "Out of stock";
    }

    var wishBtn = document.querySelector(".js-detail-wishlist-toggle");
    if (Site.isWishlisted(product.id)) wishBtn.classList.add("active");

    document.querySelector(".js-full-description").innerHTML =
      "<p>" + esc(product.description || product.short_description || "").replace(/\n/g, "</p><p>") + "</p>";
  }

  function fillSpecs(product) {
    var tbody = document.querySelector(".js-specs-table-body");
    var specs = product.specifications || [];
    if (!specs.length) {
      document.querySelector(".js-specs-empty").style.display = "";
      return;
    }
    tbody.innerHTML = specs
      .map(function (s) {
        return "<tr><th>" + Site.escapeHtml(s.name) + "</th><td><p>" + Site.escapeHtml(s.value) + "</p></td></tr>";
      })
      .join("");
  }

  function fillVendor(product) {
    var v = product.vendor;
    document.querySelector(".js-vendor-name").textContent = v.store_name;
    document.querySelector(".js-vendor-link").href = "/shop/grid-left/?vendor=" + encodeURIComponent(v.slug);
    if (v.logo) document.querySelector(".js-vendor-logo").src = v.logo;
    Api.get("vendors/" + v.slug + "/").then(function (full) {
      document.querySelector(".js-vendor-product-count").textContent = full.product_count + " products";
      document.querySelector(".js-vendor-address").textContent = full.address || "-";
      document.querySelector(".js-vendor-phone").textContent = full.phone || "-";
      document.querySelector(".js-vendor-description").textContent = full.description || "";
    });
  }

  function renderReviews(data) {
    var esc = Site.escapeHtml;
    document.querySelectorAll(".js-reviews-tab-count").forEach(function (el) {
      el.textContent = data.count;
    });
    var list = document.querySelector(".js-reviews-list");
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

    var sum = 0;
    var counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    data.results.forEach(function (r) {
      sum += r.score;
      counts[r.score] = (counts[r.score] || 0) + 1;
    });
    var total = data.results.length;
    if (total) {
      var avg = sum / total;
      document.querySelector(".js-summary-rating").style.width = (avg / 5) * 100 + "%";
      document.querySelector(".js-summary-rating-text").textContent = avg.toFixed(1) + " out of 5";
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
      document.querySelector(".js-rating-breakdown").innerHTML = html;
    }
  }

  function loadReviews() {
    return Api.get("products/" + slug + "/reviews/").then(renderReviews);
  }

  function wireActions() {
    document.querySelector(".js-qty-down").addEventListener("click", function (e) {
      e.preventDefault();
      var input = document.querySelector(".js-qty-input");
      input.value = Math.max(1, (parseInt(input.value, 10) || 1) - 1);
    });
    document.querySelector(".js-qty-up").addEventListener("click", function (e) {
      e.preventDefault();
      var input = document.querySelector(".js-qty-input");
      input.value = (parseInt(input.value, 10) || 1) + 1;
    });
    document.querySelector(".js-detail-add-to-cart").addEventListener("click", function (e) {
      e.preventDefault();
      if (!currentProduct) return;
      var qty = parseInt(document.querySelector(".js-qty-input").value, 10) || 1;
      Site.addToCart(currentProduct.id, qty);
    });
    document.querySelector(".js-detail-wishlist-toggle").addEventListener("click", function (e) {
      e.preventDefault();
      if (!currentProduct) return;
      Site.toggleWishlist(currentProduct.id).then(function () {
        e.target.closest(".js-detail-wishlist-toggle").classList.toggle("active", Site.isWishlisted(currentProduct.id));
      });
    });

    var form = document.getElementById("reviewForm");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!Site.isAuthenticated()) {
        Site.goToLogin();
        return;
      }
      var score = parseInt(document.getElementById("review-score").value, 10);
      var comment = document.getElementById("review-comment").value.trim();
      var msgBox = document.querySelector(".js-review-form-message");
      Api.post("products/" + slug + "/reviews/", { score: score, comment: comment })
        .then(function () {
          msgBox.style.display = "";
          msgBox.classList.remove("text-danger");
          msgBox.classList.add("text-success");
          msgBox.textContent = "Thanks! Your review was submitted and is pending approval.";
          document.getElementById("review-comment").value = "";
          loadReviews();
        })
        .catch(function (err) {
          msgBox.style.display = "";
          msgBox.classList.add("text-danger");
          msgBox.textContent = err.message || "Could not submit review.";
        });
    });

    if (!Site.isAuthenticated || !window.Site.isAuthenticated()) {
      // handled after Site.ready() resolves below
    }
  }

  function loadRelatedProducts(product) {
    var container = document.querySelector(".js-related-products");
    if (!container) return;
    Api.get("products/", { category: product.category.slug, page_size: 8 })
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
      .catch(function () {
        container.innerHTML = "";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireActions();
    Site.ready().then(function () {
      if (!Site.isAuthenticated()) {
        document.querySelector(".js-review-form-wrap").style.display = "none";
        document.querySelector(".js-review-login-prompt").style.display = "";
      }
      Api.get("products/" + slug + "/")
        .then(function (product) {
          currentProduct = product;
          fillGallery(product);
          fillBuyBox(product);
          fillSpecs(product);
          fillVendor(product);
          loadRelatedProducts(product);
          return loadReviews();
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
