(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  // Account details (profile form) is shown for every role. The
  // dashboard greeting, orders list and address book below are
  // customer-only sections of page-account.html (wrapped in
  // {% if not is_vendor %}), so they simply aren't in the DOM on a
  // vendor's account page -- each is looked up and used defensively
  // rather than gating the whole script on any one of them existing.
  var greeting = document.querySelector(".js-account-greeting");

  function loadMeAndFillProfile() {
    var user = Site.getUser();
    if (!user) return;
    if (greeting) {
      greeting.textContent = "Hello " + (user.profile.display_name || user.username) + "!";
    }
    document.getElementById("profile-first-name").value = user.profile.first_name || "";
    document.getElementById("profile-last-name").value = user.profile.last_name || "";
    document.getElementById("profile-display-name").value = user.profile.display_name || "";
    document.getElementById("profile-phone").value = user.profile.phone || "";
  }

  function loadOrders() {
    var body = document.querySelector(".js-orders-body");
    if (!body) return;
    Api.get("orders/").then(function (data) {
      if (!data.results.length) {
        body.innerHTML = '<tr><td colspan="5">You have not placed any orders yet.</td></tr>';
        return;
      }
      body.innerHTML = data.results
        .map(function (order) {
          return (
            "<tr><td>" +
            order.order_number +
            "</td><td>" +
            new Date(order.created_date).toLocaleDateString() +
            "</td><td>" +
            order.status +
            "</td><td>$" +
            order.total_amount +
            '</td><td><a href="/orders/invoice/' +
            encodeURIComponent(order.order_number) +
            '/" class="btn-small d-block">View</a></td></tr>'
          );
        })
        .join("");
    });
  }

  function addressCardHtml(addr) {
    return (
      '<div class="col-lg-6 mb-3"><div class="card"><div class="card-header d-flex justify-content-between"><h5 class="mb-0">' +
      (addr.is_default ? "Default Address" : "Address") +
      '</h5><a href="#" class="btn-small js-delete-address" data-id="' +
      addr.id +
      '">Delete</a></div><div class="card-body"><address>' +
      Site.escapeHtml(addr.full_name) +
      "<br/>" +
      Site.escapeHtml(addr.address_line1) +
      "<br/>" +
      Site.escapeHtml(addr.city) +
      ", " +
      Site.escapeHtml(addr.postal_code) +
      "<br/>" +
      Site.escapeHtml(addr.country) +
      "<br/>Phone: " +
      Site.escapeHtml(addr.phone) +
      "</address></div></div></div>"
    );
  }

  function loadAddresses() {
    var container = document.querySelector(".js-addresses-container");
    if (!container) return;
    Api.get("addresses/", { page_size: 50 }).then(function (data) {
      if (!data.results.length) {
        container.innerHTML = '<div class="col-12"><p>No saved addresses yet.</p></div>';
        return;
      }
      container.innerHTML = data.results.map(addressCardHtml).join("");
    });
  }

  document.addEventListener("click", function (e) {
    var del = e.target.closest(".js-delete-address");
    if (!del) return;
    e.preventDefault();
    Api.delete("addresses/" + del.getAttribute("data-id") + "/")
      .then(loadAddresses)
      .catch(function (err) {
        Site.showToast(err.message || "Could not delete this address.", "danger");
      });
  });

  // Dashboard quick links just switch to the relevant sidebar tab
  // (reuses the sidebar's own working data-bs-toggle="tab" link instead
  // of re-implementing tab switching here).
  document.addEventListener("click", function (e) {
    var link = e.target.closest(".js-dashboard-tab-link");
    if (!link) return;
    e.preventDefault();
    var tab = document.getElementById(link.getAttribute("data-target"));
    if (tab) tab.click();
  });

  function renderTrackResult(order) {
    var container = document.querySelector(".js-track-result");
    var itemsHtml = (order.items || [])
      .map(function (item) {
        return (
          "<li>" +
          Site.escapeHtml(item.product_name) +
          " &times; " +
          item.quantity +
          "</li>"
        );
      })
      .join("");
    container.innerHTML =
      '<div class="card mt-3"><div class="card-body">' +
      "<p><strong>Order:</strong> " +
      Site.escapeHtml(order.order_number) +
      "</p>" +
      "<p><strong>Status:</strong> " +
      Site.escapeHtml(order.status) +
      "</p>" +
      (order.tracking_code
        ? "<p><strong>Tracking code:</strong> " +
          Site.escapeHtml(order.tracking_code) +
          "</p>"
        : "") +
      "<p><strong>Placed on:</strong> " +
      new Date(order.created_date).toLocaleDateString() +
      "</p>" +
      "<p><strong>Total:</strong> " +
      Site.formatMoney(order.total_amount) +
      "</p>" +
      '<ul class="mb-3">' +
      itemsHtml +
      "</ul>" +
      '<a class="btn-small d-inline-block" href="/orders/invoice/' +
      encodeURIComponent(order.order_number) +
      '/">View full invoice</a>' +
      "</div></div>";
  }

  var trackOrderForm = document.getElementById("trackOrderForm");
  if (trackOrderForm) {
    trackOrderForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var container = document.querySelector(".js-track-result");
      var orderNumber = document.getElementById("track-order-number").value.trim();
      if (!orderNumber) return;
      container.innerHTML = '<p class="mt-3">Looking up your order…</p>';
      Api.get("orders/" + encodeURIComponent(orderNumber) + "/")
        .then(renderTrackResult)
        .catch(function (err) {
          var message =
            err.status === 404
              ? "No order with that number was found on your account."
              : err.message || "Could not look up that order.";
          container.innerHTML =
            '<p class="mt-3 text-danger">' + Site.escapeHtml(message) + "</p>";
        });
    });
  }

  var addAddressForm = document.getElementById("addAddressForm");
  if (addAddressForm) {
    addAddressForm.addEventListener("submit", function (e) {
      e.preventDefault();
      Api.post("addresses/", {
        full_name: document.getElementById("addr-full-name").value.trim(),
        phone: document.getElementById("addr-phone").value.trim(),
        country: document.getElementById("addr-country").value.trim(),
        city: document.getElementById("addr-city").value.trim(),
        postal_code: document.getElementById("addr-postal").value.trim(),
        address_line1: document.getElementById("addr-line1").value.trim(),
      })
        .then(function () {
          addAddressForm.reset();
          loadAddresses();
          Site.showToast("Address saved.");
        })
        .catch(function (err) {
          Site.showToast(err.message || "Could not save address.", "danger");
        });
    });
  }

  var profileForm = document.getElementById("profileForm");
  if (profileForm) {
    profileForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var msg = document.querySelector(".js-profile-message");
      Api.patch("auth/me/", {
        first_name: document.getElementById("profile-first-name").value.trim(),
        last_name: document.getElementById("profile-last-name").value.trim(),
        display_name: document.getElementById("profile-display-name").value.trim(),
        phone: document.getElementById("profile-phone").value.trim(),
      })
        .then(function () {
          msg.style.display = "";
          msg.textContent = "Profile updated.";
          Site.ready();
        })
        .catch(function (err) {
          msg.style.display = "";
          msg.className = "js-profile-message text-danger";
          msg.textContent = err.message || "Could not update profile.";
        });
    });
  }

  var passwordForm = document.getElementById("passwordForm");
  if (passwordForm) {
    passwordForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var msg = document.querySelector(".js-password-message");
      Api.post("auth/change-password/", {
        old_password: document.getElementById("password-old").value,
        new_password: document.getElementById("password-new").value,
      })
        .then(function () {
          msg.style.display = "";
          msg.className = "js-password-message text-success";
          msg.textContent = "Password changed.";
          passwordForm.reset();
        })
        .catch(function (err) {
          msg.style.display = "";
          msg.className = "js-password-message text-danger";
          msg.textContent = err.message || "Could not change password.";
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(function () {
      loadMeAndFillProfile();
      loadOrders();
      loadAddresses();
    });
  });
})(window, document);
