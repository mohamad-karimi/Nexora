(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var root = document.getElementById("js-post-detail");
  if (!root) return; // page doesn't use this script's markup
  var slug = root.getAttribute("data-post-slug");

  function formatDate(value) {
    if (!value) return "";
    var date = new Date(value);
    if (isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  }

  function readingTime(content) {
    var words = (content || "").trim().split(/\s+/).filter(Boolean).length;
    var minutes = Math.max(1, Math.round(words / 200));
    return minutes + (minutes === 1 ? " min read" : " mins read");
  }

  function fillHeader(post) {
    var esc = Site.escapeHtml;

    var categoryLink = document.querySelector(".js-post-category");
    categoryLink.textContent = post.category.name;
    categoryLink.href = "/blog/?category=" + encodeURIComponent(post.category.slug);

    document.querySelector(".js-post-title").textContent = post.title;
    document.title = post.title;

    var authorLink = document.querySelector(".js-post-author");
    if (post.author) {
      authorLink.textContent = post.author.display_name;
    } else {
      authorLink.parentNode.style.display = "none";
    }

    document.querySelector(".js-post-date").textContent = formatDate(post.created_date);
    document.querySelector(".js-post-reading-time").textContent = readingTime(post.content);
  }

  function fillBody(post) {
    var esc = Site.escapeHtml;

    var image = document.querySelector(".js-post-image");
    if (post.image) {
      image.src = post.image;
      image.alt = post.title;
    } else {
      image.closest("figure").style.display = "none";
    }

    var excerptEl = document.querySelector(".js-post-excerpt");
    if (post.excerpt) {
      excerptEl.textContent = post.excerpt;
    } else {
      excerptEl.style.display = "none";
    }

    var contentEl = document.querySelector(".js-post-content");
    var paragraphs = (post.content || "").split(/\n\s*\n/).filter(function (p) {
      return p.trim().length;
    });
    contentEl.innerHTML = paragraphs.length
      ? paragraphs.map(function (p) { return "<p>" + esc(p.trim()) + "</p>"; }).join("")
      : "";
  }

  function fillTags(post) {
    var row = document.querySelector(".js-post-tags-row");
    var tags = post.tags || [];
    if (!tags.length) return;
    row.style.display = "";
    document.querySelector(".js-post-tags").innerHTML = tags
      .map(function (tag) {
        return (
          '<a href="/blog/?tag=' +
          encodeURIComponent(tag.slug) +
          '" rel="tag" class="hover-up btn btn-sm btn-rounded mr-10">' +
          Site.escapeHtml(tag.name) +
          "</a>"
        );
      })
      .join("");
  }

  function fillAuthorBio(post) {
    if (!post.author) return;
    var box = document.querySelector(".js-post-author-bio");
    box.style.display = "";
    document.querySelector(".js-post-author-bio-name").textContent = post.author.display_name;
  }

  document.addEventListener("DOMContentLoaded", function () {
    Api.get("blog/posts/" + encodeURIComponent(slug) + "/")
      .then(function (post) {
        fillHeader(post);
        fillBody(post);
        fillTags(post);
        fillAuthorBio(post);
      })
      .catch(function (error) {
        root.innerHTML =
          '<div class="col-12 text-center py-5"><p class="mb-0">' +
          Site.escapeHtml(error.message || "Post not found.") +
          "</p></div>";
      });
  });
})(window, document);
