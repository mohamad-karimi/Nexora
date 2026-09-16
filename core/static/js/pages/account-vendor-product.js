/**
 * Vendor-only "Add Product" panel on the Vendor Account page
 * (accounts:account, #add-product tab). Only loaded by the template
 * when `is_vendor` is true, so it doesn't need its own role check --
 * the real enforcement is server-side (IsVerified + IsVendor on
 * /api/v1/vendors/dashboard/products/, see api.v1.views.vendors).
 */
(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var form = document.getElementById("vendorAddProductForm");
  if (!form) return;

  var categorySelect = document.getElementById("product-category");
  var message = document.querySelector(".js-add-product-message");
  var productsBody = document.querySelector(".js-vendor-products-body");

  function showMessage(text, isError) {
    if (!message) return;
    message.style.display = "";
    message.className = "js-add-product-message " + (isError ? "text-danger" : "text-success");
    message.textContent = text;
  }

  function loadCategories() {
    if (!categorySelect) return;
    Api.get("categories/", { page_size: 100 }).then(function (data) {
      (data.results || []).forEach(function (category) {
        var option = document.createElement("option");
        option.value = category.id;
        option.textContent = category.name;
        categorySelect.appendChild(option);
      });
    });
  }

  function statusLabel(status) {
    if (!status) return "";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function productRowHtml(product) {
    return (
      "<tr><td>" +
      Site.escapeHtml(product.name) +
      "</td><td>" +
      Site.escapeHtml((product.category && product.category.name) || "") +
      "</td><td>" +
      Site.formatMoney(product.price) +
      "</td><td>" +
      product.stock +
      "</td><td>" +
      Site.escapeHtml(statusLabel(product.status)) +
      "</td></tr>"
    );
  }

  function loadVendorProducts() {
    if (!productsBody) return;
    Api.get("vendors/dashboard/products/", { page_size: 20 }).then(function (data) {
      if (!data.results.length) {
        productsBody.innerHTML = '<tr><td colspan="5">You have not added any products yet.</td></tr>';
        return;
      }
      productsBody.innerHTML = data.results.map(productRowHtml).join("");
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

    var imageInput = document.getElementById("product-image");
    if (imageInput.files && imageInput.files[0]) {
      formData.append("image", imageInput.files[0]);
    }

    var submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;

    Api.post("vendors/dashboard/products/", formData)
      .then(function () {
        showMessage("Product created successfully.", false);
        Site.showToast("Product created successfully.");
        form.reset();
        loadVendorProducts();
      })
      .catch(function (err) {
        showMessage(err.message || "Could not create the product.", true);
      })
      .finally(function () {
        submitButton.disabled = false;
      });
  });

  document.addEventListener("DOMContentLoaded", function () {
    loadCategories();
    loadVendorProducts();
  });
})(window, document);
