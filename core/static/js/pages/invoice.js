(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;

  var orderNumber = document.body.getAttribute("data-order-number");
  if (!orderNumber) return;

  function rowHtml(item) {
    return (
      "<tr><td><div class=\"item-desc-1\"><span>" +
      Site.escapeHtml(item.product_name) +
      "</span></div></td><td class=\"text-center\">" +
      Site.formatMoney(item.unit_price) +
      '</td><td class="text-center">' +
      item.quantity +
      '</td><td class="text-right">' +
      Site.formatMoney(item.total_price) +
      "</td></tr>"
    );
  }

  function render(order) {
    document.querySelector(".js-invoice-number").textContent = order.order_number;
    document.querySelector(".js-invoice-date").textContent =
      "Date: " + new Date(order.created_date).toLocaleDateString();
    document.querySelector(".js-invoice-status").textContent = order.status;
    document.querySelector(".js-invoice-payment-method").textContent =
      order.payments.length ? order.payments[0].payment_method : "-";

    var addr = order.shipping_address;
    document.querySelector(".js-invoice-to").innerHTML =
      "<strong>" +
      Site.escapeHtml(addr.full_name) +
      "</strong><br/>" +
      Site.escapeHtml(addr.phone) +
      "<br/>" +
      Site.escapeHtml(addr.address_line1) +
      ", " +
      Site.escapeHtml(addr.city) +
      ", " +
      Site.escapeHtml(addr.country);

    document.querySelector(".js-invoice-items").innerHTML = order.items.map(rowHtml).join("");
    document.querySelector(".js-invoice-subtotal").textContent = Site.formatMoney(order.subtotal);
    document.querySelector(".js-invoice-shipping").textContent =
      parseFloat(order.shipping_cost) === 0 ? "Free" : Site.formatMoney(order.shipping_cost);
    if (parseFloat(order.discount_amount) > 0) {
      document.querySelector(".js-invoice-discount-row").style.display = "";
      document.querySelector(".js-invoice-discount").textContent = "-" + Site.formatMoney(order.discount_amount);
    }
    document.querySelector(".js-invoice-total").textContent = Site.formatMoney(order.total_amount);
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(function () {
      Api.get("orders/" + encodeURIComponent(orderNumber) + "/")
        .then(render)
        .catch(function (error) {
          document.querySelector(".invoice-info").innerHTML =
            '<div class="text-center py-5"><p>' +
            Site.escapeHtml(error.message || "Order not found.") +
            "</p></div>";
        });
    });
  });
})(window, document);
