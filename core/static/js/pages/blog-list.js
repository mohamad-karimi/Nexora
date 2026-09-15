(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  /**
   * Populates the "Category" and "Trending Now" widgets in
   * templates/blog/sidebar.html (included on this page). The markup
   * used to ship with hardcoded shop categories/products whose links
   * pointed at shop-grid_left and at the original HTML theme's
   * external demo site (nest-frontend-v6.vercel.app) - dead ends
   * inside this Django project, and the wrong content type for a
   * blog sidebar besides. This mirrors the same
   * categories/new-products loading already used on the shop listing
   * page (see static/js/pages/shop-list.js) so the widgets show real
   * blog data and link to real pages.
   */
  function loadSidebarCategories() {
    var list = document.querySelector(".js-category-list");
    if (!list) return;

    Api.get("blog/categories/", { page_size: 100 }).then(function (data) {
      list.innerHTML = data.results
        .map(function (category) {
          return (
            '<li><a href="/blog/?category=' +
            encodeURIComponent(category.slug) +
            '">' +
            Site.escapeHtml(category.name) +
            '</a><span class="count">' +
            category.post_count +
            "</span></li>"
          );
        })
        .join("");
    });
  }

  function loadSidebarTags() {
    var list = document.querySelector(".js-sidebar-tags");
    if (!list) return;

    Api.get("blog/tags/", { page_size: 100 }).then(function (data) {
      list.innerHTML = data.results
        .map(function (tag) {
          return (
            '<li class="hover-up"><a href="/blog/?tag=' +
            encodeURIComponent(tag.slug) +
            '"><i class="fi-rs-cross mr-10"></i>' +
            Site.escapeHtml(tag.name) +
            "</a></li>"
          );
        })
        .join("");
    });
  }

  function loadSidebarTrendingPosts() {
    var container = document.querySelector(".js-sidebar-trending-posts");
    if (!container) return;

    Api.get("blog/posts/", { ordering: "-created_date", page_size: 4 }).then(
      function (data) {
        container.innerHTML = data.results
          .map(function (post) {
            var url = "/blog/post/" + encodeURIComponent(post.slug) + "/";
            return (
              '<div class="single-post clearfix"><div class="image"><a href="' +
              url +
              '">' +
              (post.image
                ? '<img src="' +
                  post.image +
                  '" alt="' +
                  Site.escapeHtml(post.title) +
                  '" />'
                : "") +
              '</a></div><div class="content pt-10"><h6><a href="' +
              url +
              '">' +
              Site.escapeHtml(post.title) +
              '</a></h6><p class="mb-0 mt-5 font-xs color-grey">' +
              formatDate(post.created_date) +
              "</p></div></div>"
            );
          })
          .join("");
      }
    );
  }

  var grid = document.querySelector(".js-blog-grid");
  if (!grid) return; // page doesn't use this script's markup

  var state = {
    category: "",
    tag: "",
    q: "",
    ordering: "-created_date",
    page: 1,
    page_size: 6,
  };

  function readStateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    state.category = params.get("category") || "";
    state.tag = params.get("tag") || "";
    state.q = params.get("q") || "";
    state.ordering = params.get("ordering") || "-created_date";
    state.page = parseInt(params.get("page"), 10) || 1;
    state.page_size = parseInt(params.get("page_size"), 10) || 6;
  }

  function pushStateToUrl() {
    var params = new URLSearchParams();
    if (state.category) params.set("category", state.category);
    if (state.tag) params.set("tag", state.tag);
    if (state.q) params.set("q", state.q);
    if (state.ordering && state.ordering !== "-created_date") params.set("ordering", state.ordering);
    if (state.page > 1) params.set("page", state.page);
    if (state.page_size !== 6) params.set("page_size", state.page_size);
    var query = params.toString();
    var url = window.location.pathname + (query ? "?" + query : "");
    window.history.replaceState({}, "", url);
  }

  function formatDate(value) {
    if (!value) return "";
    var date = new Date(value);
    if (isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  }

  function postCardHtml(post) {
    var esc = Site.escapeHtml;
    var url = "/blog/post/" + encodeURIComponent(post.slug) + "/";
    var img = post.image || "/static/imgs/blog/blog-1.png";
    var authorName = post.author ? esc(post.author.display_name) : "";

    return (
      '<article class="wow fadeIn animated hover-up mb-30 animated">' +
      '<div class="post-thumb" style="background-image: url(' +
      img +
      ')">' +
      '<div class="entry-meta">' +
      '<a class="entry-meta meta-2" href="/blog/?category=' +
      encodeURIComponent(post.category.slug) +
      '"><i class="fi-rs-apps"></i></a>' +
      "</div>" +
      "</div>" +
      '<div class="entry-content-2 pl-50">' +
      '<h3 class="post-title mb-20">' +
      '<a href="' +
      url +
      '">' +
      esc(post.title) +
      "</a>" +
      "</h3>" +
      '<p class="post-exerpt mb-40">' +
      esc(post.excerpt) +
      "</p>" +
      '<div class="entry-meta meta-1 font-xs color-grey mt-10 pb-10">' +
      "<div>" +
      '<span class="post-on">' +
      formatDate(post.created_date) +
      "</span>" +
      (authorName ? '<span class="hit-count has-dot">By ' + authorName + "</span>" : "") +
      "</div>" +
      '<a href="' +
      url +
      '" class="text-brand font-heading font-weight-bold">Read more <i class="fi-rs-arrow-right"></i></a>' +
      "</div>" +
      "</div>" +
      "</article>"
    );
  }

  function renderPosts(data) {
    if (!data.results.length) {
      grid.innerHTML = '<p class="mb-0">No posts match your filters.</p>';
    } else {
      grid.innerHTML = data.results.map(postCardHtml).join("");
    }
    renderPagination(data.count);
  }

  function renderPagination(count) {
    var container = document.querySelector(".js-pagination");
    if (!container) return;
    var totalPages = Math.max(1, Math.ceil(count / state.page_size));
    if (totalPages <= 1) {
      container.innerHTML = "";
      return;
    }
    var html = "";
    html +=
      '<li class="page-item"><a class="page-link js-page-link" data-page="' +
      Math.max(1, state.page - 1) +
      '" href="#"><i class="fi-rs-arrow-small-left"></i></a></li>';

    var start = Math.max(1, state.page - 2);
    var end = Math.min(totalPages, start + 4);
    start = Math.max(1, Math.min(start, end - 4));

    for (var p = start; p <= end; p++) {
      html +=
        '<li class="page-item ' +
        (p === state.page ? "active" : "") +
        '"><a class="page-link js-page-link" data-page="' +
        p +
        '" href="#">' +
        p +
        "</a></li>";
    }
    html +=
      '<li class="page-item"><a class="page-link js-page-link" data-page="' +
      Math.min(totalPages, state.page + 1) +
      '" href="#"><i class="fi-rs-arrow-small-right"></i></a></li>';
    container.innerHTML = html;
  }

  function loadPosts() {
    grid.innerHTML = '<p class="mb-0">Loading posts…</p>';
    return Api.get("blog/posts/", {
      category: state.category || undefined,
      tag: state.tag || undefined,
      search: state.q || undefined,
      ordering: state.ordering,
      page: state.page,
      page_size: state.page_size,
    })
      .then(function (data) {
        renderPosts(data);
      })
      .catch(function (error) {
        grid.innerHTML =
          '<p class="mb-0 text-danger">' +
          Site.escapeHtml(error.message || "Could not load posts.") +
          "</p>";
      });
  }

  function wireEvents() {
    document.addEventListener("click", function (event) {
      var pageSizeOption = event.target.closest(".js-page-size-option");
      if (pageSizeOption) {
        event.preventDefault();
        state.page_size = parseInt(pageSizeOption.getAttribute("data-value"), 10) || 50;
        state.page = 1;
        document.querySelectorAll(".js-page-size-option").forEach(function (a) {
          a.classList.toggle("active", a === pageSizeOption);
        });
        var label = document.querySelector(".js-page-size-label");
        if (label) label.innerHTML = " " + pageSizeOption.textContent + ' <i class="fi-rs-angle-small-down"></i>';
        pushStateToUrl();
        loadPosts();
        return;
      }

      var sortOption = event.target.closest(".js-sort-option");
      if (sortOption) {
        event.preventDefault();
        state.ordering = sortOption.getAttribute("data-value");
        state.page = 1;
        document.querySelectorAll(".js-sort-option").forEach(function (a) {
          a.classList.toggle("active", a === sortOption);
        });
        var sortLabel = document.querySelector(".js-sort-label");
        if (sortLabel) sortLabel.innerHTML = " " + sortOption.textContent + ' <i class="fi-rs-angle-small-down"></i>';
        pushStateToUrl();
        loadPosts();
        return;
      }

      var pageLink = event.target.closest(".js-page-link");
      if (pageLink) {
        event.preventDefault();
        state.page = parseInt(pageLink.getAttribute("data-page"), 10) || 1;
        pushStateToUrl();
        loadPosts();
        window.scrollTo({ top: grid.offsetTop - 100, behavior: "smooth" });
        return;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    readStateFromUrl();
    wireEvents();
    loadPosts();
    loadSidebarCategories();
    loadSidebarTrendingPosts();
    loadSidebarTags();
  });
})(window, document);
