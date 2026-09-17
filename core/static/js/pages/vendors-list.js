(function (window, document) {
  "use strict";
  var Api = window.Api;
  var Site = window.Site;
  var grid = document.querySelector(".js-vendor-grid");
  if (!grid) return;

  // page_size starts at 50 to match the "Show:" dropdown's default
  // selection (marked .active in the template); ordering left unset so
  // the API's own default (store_name, see VendorViewSet.ordering)
  // applies, matching the "Sort by: Name" default option.
  var state = { search: "", page: 1, page_size: 50, ordering: undefined };

  function cardHtml(v) {
    var esc = Site.escapeHtml;
    var url = "/shop/grid-left/?vendor=" + encodeURIComponent(v.slug);
    return (
      '<div class="col-lg-3 col-md-6 col-12 col-sm-6"><div class="vendor-wrap mb-40">' +
      '<div class="vendor-img-action-wrap"><div class="vendor-img"><a href="' +
      url +
      '">' +
      (v.logo ? '<img src="' + v.logo + '" alt="' + esc(v.store_name) + '" />' : "") +
      '</a></div><div class="vendor-content-wrap"><h5><a href="' +
      url +
      '">' +
      esc(v.store_name) +
      '</a></h5><p class="font-sm">' +
      v.product_count +
      ' products</p><p class="font-xs text-muted">' +
      esc(v.address || "") +
      '</p><p class="font-xs text-muted">' +
      esc(v.phone || "") +
      '</p><a href="' +
      url +
      '" class="btn mt-10">Visit Store</a></div></div></div></div>'
    );
  }

  function render(data) {
    if (!data.results.length) {
      grid.innerHTML = '<div class="col-12 text-center py-5">No vendors found.</div>';
    } else {
      grid.innerHTML = data.results.map(cardHtml).join("");
    }
    document.querySelectorAll(".totall-product strong").forEach(function (el) {
      el.textContent = data.count;
    });
    renderPagination(data.count);
  }

  function renderPagination(count) {
    var container = document.querySelector(".js-vendor-pagination");
    if (!container) return;
    var totalPages = Math.max(1, Math.ceil(count / state.page_size));
    if (totalPages <= 1) {
      container.innerHTML = "";
      return;
    }
    var html = "";
    for (var p = 1; p <= totalPages; p++) {
      html +=
        '<li class="page-item ' +
        (p === state.page ? "active" : "") +
        '"><a class="page-link js-vpage" data-page="' +
        p +
        '" href="#">' +
        p +
        "</a></li>";
    }
    container.innerHTML = html;
  }

  function load() {
    return Api.get("vendors/", {
      search: state.search || undefined,
      page: state.page,
      page_size: state.page_size,
      ordering: state.ordering || undefined,
    }).then(render);
  }

  function setActive(container, link) {
    container.querySelectorAll("a").forEach(function (a) {
      a.classList.remove("active");
    });
    link.classList.add("active");
  }

  document.addEventListener("click", function (e) {
    var pageLink = e.target.closest(".js-vpage");
    if (pageLink) {
      e.preventDefault();
      state.page = parseInt(pageLink.getAttribute("data-page"), 10) || 1;
      load();
      return;
    }

    var showLink = e.target.closest(".js-show-option");
    if (showLink) {
      e.preventDefault();
      // "All" reuses the API's max_page_size (see StandardPagination) as
      // its real, supported upper bound -- not an unlimited/fake fetch.
      state.page_size =
        parseInt(showLink.getAttribute("data-page-size"), 10) || state.page_size;
      state.page = 1;
      setActive(showLink.closest(".sort-by-dropdown"), showLink);
      var showLabel = document.querySelector(".js-show-label");
      if (showLabel) {
        var showText =
          showLink.getAttribute("data-page-size-label") || showLink.textContent.trim();
        showLabel.innerHTML = " " + showText + ' <i class="fi-rs-angle-small-down"></i>';
      }
      load();
      return;
    }

    var sortLink = e.target.closest(".js-sort-option");
    if (sortLink) {
      e.preventDefault();
      state.ordering = sortLink.getAttribute("data-ordering") || undefined;
      state.page = 1;
      setActive(sortLink.closest(".sort-by-dropdown"), sortLink);
      var sortLabel = document.querySelector(".js-sort-label");
      if (sortLabel) {
        sortLabel.innerHTML =
          " " + sortLink.textContent.trim() + ' <i class="fi-rs-angle-small-down"></i>';
      }
      load();
      return;
    }
  });

  var form = document.getElementById("vendor-search-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      state.search = document.getElementById("vendor-search-input").value.trim();
      state.page = 1;
      load();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Site.ready().then(load);
  });
})(window, document);
