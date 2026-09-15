/**
 * Powers templates/blog/blog-post-fullwidth.html. Fetches the post by
 * slug from /api/v1/blog/posts/<slug>/ and fills in every dynamic
 * piece of the page: header (title/category/author/date/reading
 * time), image, excerpt/content, tags, author box, bookmark/like
 * buttons, share buttons, and the comment list + form.
 *
 * Bookmark and Like are two fully independent actions/endpoints
 * (blog.PostBookmark and blog.PostLike) - each has its own state,
 * its own toggle button, and its own API call. Neither one touches
 * the other's data.
 */
(function (window, document) {
  "use strict";

  var Api = window.Api;
  var Site = window.Site;

  var root = document.getElementById("js-post-detail");
  if (!root) return; // page doesn't use this script's markup
  var slug = root.getAttribute("data-post-slug");

  if (!slug) {
    // /blog/post/ (no slug) is a route that exists in blog/urls.py but
    // has nothing to fetch - fail gracefully instead of calling
    // /api/v1/blog/posts//.
    root.innerHTML =
      '<div class="col-12 text-center py-5"><p class="mb-0">No post was specified.</p></div>';
    return;
  }

  var DEFAULT_COMMENT_AVATAR = "/static/imgs/blog/author-2.png";

  function showAlert(options) {
    if (typeof window.Swal === "undefined") return;
    window.Swal.fire(options);
  }

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

  // ---- header / body / tags / author box ---------------------------------

  function setBookmarkButton(active) {
    document.querySelectorAll(".js-post-bookmark-btn").forEach(function (btn) {
      btn.classList.toggle("active", !!active);
    });
  }

  function setLikeButton(active, count) {
    document.querySelectorAll(".js-post-like-btn").forEach(function (btn) {
      btn.classList.toggle("active", !!active);
    });
    if (typeof count === "number") {
      document.querySelectorAll(".js-post-like-count").forEach(function (el) {
        el.textContent = String(count);
      });
    }
  }

  function fillHeader(post) {
    var categoryLink = document.querySelector(".js-post-category");
    categoryLink.textContent = post.category.name;
    categoryLink.href = "/blog/?category=" + encodeURIComponent(post.category.slug);

    document.querySelector(".js-post-title").textContent = post.title;
    document.title = post.title;

    var authorEl = document.querySelector(".js-post-author");
    var avatarWrap = document.querySelector(".js-post-author-avatar-wrap");
    if (post.author) {
      authorEl.textContent = post.author.display_name;
      if (post.author.avatar) {
        avatarWrap.querySelector("img").src = post.author.avatar;
      }
    } else {
      authorEl.closest(".post-by").style.display = "none";
    }

    document.querySelector(".js-post-date").textContent = formatDate(post.created_date);
    document.querySelector(".js-post-reading-time").textContent = readingTime(post.content);

    // Two independent states from two independent models - setting
    // one never touches the other.
    setBookmarkButton(post.is_bookmarked);
    setLikeButton(post.is_liked, post.like_count || 0);
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
    var bioText = document.querySelector(".js-post-author-bio-text");
    if (post.author.bio) {
      bioText.textContent = post.author.bio;
    } else {
      bioText.style.display = "none";
    }
    if (post.author.avatar) {
      document.querySelector(".js-post-author-bio-avatar").src = post.author.avatar;
    }
  }

  // ---- bookmark / like -----------------------------------------------------

  function wireBookmarkButton() {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest(".js-post-bookmark-btn");
      if (!btn) return;
      event.preventDefault();

      if (!Site.isAuthenticated()) {
        Site.goToLogin();
        return;
      }

      Api.post("blog/posts/" + encodeURIComponent(slug) + "/bookmark/")
        .then(function (data) {
          setBookmarkButton(data.bookmarked);
          Site.showToast(data.bookmarked ? "Saved to your bookmarks." : "Removed from your bookmarks.");
        })
        .catch(function (error) {
          if (error.status === 401 || error.status === 403) {
            Site.goToLogin();
          } else {
            Site.showToast(error.message || "Could not update bookmark.", "danger");
          }
        });
    });
  }

  function wireLikeButton() {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest(".js-post-like-btn");
      if (!btn) return;
      event.preventDefault();

      if (!Site.isAuthenticated()) {
        Site.goToLogin();
        return;
      }

      Api.post("blog/posts/" + encodeURIComponent(slug) + "/like/")
        .then(function (data) {
          setLikeButton(data.liked, data.like_count);
          Site.showToast(data.liked ? "Liked." : "Like removed.");
        })
        .catch(function (error) {
          if (error.status === 401 || error.status === 403) {
            Site.goToLogin();
          } else {
            Site.showToast(error.message || "Could not update like.", "danger");
          }
        });
    });
  }

  // ---- share buttons ---------------------------------------------------------

  function wireShareButtons(post) {
    var pageUrl = window.location.href;
    var title = post.title;

    function openShareWindow(url) {
      window.open(url, "_blank", "noopener,noreferrer,width=600,height=500");
    }

    var handlers = {
      "js-share-facebook": function () {
        openShareWindow("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(pageUrl));
      },
      "js-share-twitter": function () {
        openShareWindow(
          "https://twitter.com/intent/tweet?url=" + encodeURIComponent(pageUrl) + "&text=" + encodeURIComponent(title)
        );
      },
      "js-share-linkedin": function () {
        openShareWindow("https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(pageUrl));
      },
      "js-share-copy-link": function () {
        // Instagram has no web share-intent URL for arbitrary links,
        // so this copies the link instead of faking a share dialog.
        navigator.clipboard
          .writeText(pageUrl)
          .then(function () {
            Site.showToast("Link copied - paste it into Instagram.");
          })
          .catch(function () {
            Site.showToast("Could not copy the link.", "danger");
          });
      },
    };

    document.addEventListener("click", function (event) {
      Object.keys(handlers).forEach(function (className) {
        var btn = event.target.closest("." + className);
        if (btn) {
          event.preventDefault();
          handlers[className]();
        }
      });
    });
  }

  // ---- comments ---------------------------------------------------------

  function renderComments(comments) {
    var list = document.querySelector(".js-comments-list");
    document.querySelector(".js-comments-count").textContent = comments.length;

    if (!comments.length) {
      list.innerHTML = '<p class="js-comments-empty text-muted">Be the first to comment on this post.</p>';
      return;
    }

    var esc = Site.escapeHtml;
    list.innerHTML = comments
      .map(function (comment) {
        var avatar = comment.user_avatar || DEFAULT_COMMENT_AVATAR;
        return (
          '<div class="single-comment justify-content-between d-flex mb-30">' +
          '<div class="user justify-content-between d-flex">' +
          '<div class="thumb text-center">' +
          '<img src="' + esc(avatar) + '" alt="">' +
          '<span class="font-heading text-brand">' + esc(comment.user_display_name) + "</span>" +
          "</div>" +
          '<div class="desc">' +
          '<div class="d-flex justify-content-between mb-10">' +
          '<div class="d-flex align-items-center">' +
          '<span class="font-xs text-muted">' + esc(formatDate(comment.created_date)) + "</span>" +
          "</div>" +
          "</div>" +
          '<p class="mb-10">' + esc(comment.content) + "</p>" +
          "</div>" +
          "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  function loadComments() {
    return Api.get("blog/posts/" + encodeURIComponent(slug) + "/comments/", { page_size: 50 }).then(
      function (data) {
        renderComments(data.results || []);
      }
    );
  }

  function showCommentFormMessage(message) {
    var box = document.querySelector(".js-comment-form-message");
    if (!message) {
      box.style.display = "none";
      box.textContent = "";
      return;
    }
    box.textContent = message;
    box.style.display = "";
  }

  function wireCommentForm() {
    var form = document.getElementById("commentForm");
    var loginPrompt = document.querySelector(".js-comment-login-prompt");

    Site.ready().then(function () {
      var authed = Site.isAuthenticated();
      form.style.display = authed ? "" : "none";
      loginPrompt.style.display = authed ? "none" : "";
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showCommentFormMessage("");

      var textarea = document.getElementById("comment");
      var content = textarea.value.trim();
      if (!content) {
        showCommentFormMessage("Please write a comment before posting.");
        return;
      }

      var submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;

      Api.post("blog/posts/" + encodeURIComponent(slug) + "/comments/", { content: content })
        .then(function () {
          textarea.value = "";
          showAlert({ icon: "success", title: "Comment posted", text: "Thanks for sharing your thoughts!" });
          Site.showToast("Comment posted.");
          return loadComments();
        })
        .catch(function (error) {
          if (error.status === 401 || error.status === 403) {
            Site.goToLogin();
            return;
          }
          var message = error.message || "Could not post your comment.";
          showCommentFormMessage(message);
          showAlert({ icon: "error", title: "Something went wrong", text: message });
        })
        .finally(function () {
          submitBtn.disabled = false;
        });
    });
  }

  // ---- init ---------------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    Api.get("blog/posts/" + encodeURIComponent(slug) + "/")
      .then(function (post) {
        fillHeader(post);
        fillBody(post);
        fillTags(post);
        fillAuthorBio(post);
        wireBookmarkButton();
        wireLikeButton();
        wireShareButtons(post);
        wireCommentForm();
        return loadComments();
      })
      .catch(function (error) {
        root.innerHTML =
          '<div class="col-12 text-center py-5"><p class="mb-0">' +
          Site.escapeHtml(error.message || "Post not found.") +
          "</p></div>";
      });
  });
})(window, document);
