/**
 * Vendor-only "Edit Product" page (dashboard:product-edit).
 *
 * The page itself only checks the visitor is a vendor (see
 * dashboard.views.ProductEditView) -- it does NOT check they own the
 * product in the URL. Ownership is enforced entirely by the API: both
 * the GET that loads the product and the PUT that saves it go through
 * /api/v1/vendors/dashboard/products/<slug>/, which only ever resolves
 * against the current vendor's own products (see
 * api.v1.views.vendors.VendorDashboardProductDetailView). A slug that
 * belongs to another vendor's product 404s exactly like an unknown
 * slug would -- this script just surfaces that as a "not found"
 * message and never renders another vendor's data into the form.
 *
 * `vendor` and `published` are never part of this form: the API
 * endpoint doesn't expose them at all, so nothing submitted here can
 * move the product to another store or publish it.
 */
(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var form = document.getElementById("vendorEditProductForm");
  if (!form) return; // not the edit product page

  var slug = form.getAttribute("data-product-slug") || "";
  var categorySelect = document.getElementById("product-category");
  var message = document.querySelector(".js-edit-product-message");
  var submitButton = form.querySelector(".js-edit-product-submit");
  var currentImageWrap = document.querySelector(".js-current-image-wrap");
  var currentImage = document.querySelector(".js-current-image");
  var titleEl = document.querySelector(".js-edit-product-title");

  function showMessage(text, isError) {
    if (!message) return;
    message.style.display = "";
    message.className = "js-edit-product-message " + (isError ? "text-danger" : "text-success");
    message.textContent = text;
  }

  function disableForm(disabled) {
    Array.prototype.forEach.call(form.elements, function (el) {
      el.disabled = disabled;
    });
  }

  function loadCategories() {
    if (!categorySelect) return Promise.resolve();
    return Api.get("categories/", { page_size: 100 }).then(function (data) {
      (data.results || []).forEach(function (category) {
        var option = document.createElement("option");
        option.value = category.id;
        option.textContent = category.name;
        categorySelect.appendChild(option);
      });
    });
  }

  // "2024-06-01T14:30:00Z" / with offset -> "2024-06-01T14:30" for a
  // <input type="datetime-local">, in the browser's local time.
  function toDatetimeLocalValue(isoString) {
    if (!isoString) return "";
    var date = new Date(isoString);
    if (isNaN(date.getTime())) return "";
    var pad = function (n) {
      return n < 10 ? "0" + n : "" + n;
    };
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate()) +
      "T" +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  function setValue(id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value === null || value === undefined ? "" : value;
  }

  function populateForm(product) {
    if (titleEl) titleEl.textContent = "Edit Product — " + product.name;
    setValue("product-name", product.name);
    setValue("product-sku", product.sku);
    setValue("product-price", product.price);
    setValue("product-discount-percent", product.discount_percent);
    setValue("product-discount-end", toDatetimeLocalValue(product.discount_end));
    setValue("product-stock", product.stock);
    setValue("product-condition", product.condition);
    setValue("product-status", product.status);
    setValue("product-color", product.color);
    setValue("product-short-description", product.short_description);
    setValue("product-description", product.description);
    setValue("product-type", product.product_type);
    setValue("product-manufacture-date", product.manufacture_date);
    setValue("product-shelf-life-days", product.shelf_life_days);

    if (categorySelect && product.category) {
      categorySelect.value = String(product.category);
    }

    if (product.image && currentImage && currentImageWrap) {
      currentImage.src = product.image;
      currentImage.alt = product.name;
      currentImageWrap.style.display = "";
    }
  }

  function loadProduct() {
    if (!slug) {
      showMessage("No product was specified.", true);
      disableForm(true);
      return;
    }
    Promise.all([loadCategories(), Api.get("vendors/dashboard/products/" + encodeURIComponent(slug) + "/")])
      .then(function (results) {
        populateForm(results[1]);
      })
      .catch(function (err) {
        // Covers both "no such product" and "exists but belongs to a
        // different vendor" -- the API can't tell those apart on
        // purpose, so neither can this message.
        disableForm(true);
        if (err && err.status === 404) {
          showMessage(
            "This product could not be found, or you don't have permission to edit it.",
            true
          );
        } else {
          showMessage(err.message || "Could not load this product right now.", true);
        }
      });
  }

  function appendIfPresent(formData, key, value) {
    if (value === null || value === undefined || value === "") return;
    formData.append(key, value);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    var name = document.getElementById("product-name").value.trim();
    var category = document.getElementById("product-category").value;
    var sku = document.getElementById("product-sku").value.trim();
    var price = document.getElementById("product-price").value;

    if (!name || !category || !sku || !price) {
      showMessage("Please fill in Product Name, Category, SKU and Price.", true);
      return;
    }

    var formData = new FormData();
    formData.append("name", name);
    formData.append("category", category);
    formData.append("sku", sku);
    formData.append("price", price);

    appendIfPresent(formData, "discount_percent", document.getElementById("product-discount-percent").value);
    appendIfPresent(formData, "discount_end", document.getElementById("product-discount-end").value);
    appendIfPresent(formData, "stock", document.getElementById("product-stock").value);
    appendIfPresent(formData, "condition", document.getElementById("product-condition").value);
    appendIfPresent(formData, "status", document.getElementById("product-status").value);
    appendIfPresent(formData, "color", document.getElementById("product-color").value);
    appendIfPresent(formData, "short_description", document.getElementById("product-short-description").value.trim());
    appendIfPresent(formData, "description", document.getElementById("product-description").value.trim());
    appendIfPresent(formData, "product_type", document.getElementById("product-type").value.trim());
    appendIfPresent(formData, "manufacture_date", document.getElementById("product-manufacture-date").value);
    appendIfPresent(formData, "shelf_life_days", document.getElementById("product-shelf-life-days").value);

    // Only send a new image file if the vendor picked one; omitting the
    // field entirely (rather than sending it empty) is what tells the
    // API to leave the existing image alone.
    var imageInput = document.getElementById("product-image");
    if (imageInput.files && imageInput.files[0]) {
      formData.append("image", imageInput.files[0]);
    }

    submitButton.disabled = true;

    Api.put("vendors/dashboard/products/" + encodeURIComponent(slug) + "/", formData)
      .then(function () {
        showMessage("Product updated successfully.", false);
        Site.showToast("Product updated successfully.");
        setTimeout(function () {
          window.location.href = "/dashboard/";
        }, 1200);
      })
      .catch(function (err) {
        showMessage(err.message || "Could not update the product.", true);
        submitButton.disabled = false;
      });
  });

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(loadProduct);
  });
})(window, document);
