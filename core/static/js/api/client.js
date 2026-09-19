/**
 * Minimal fetch() wrapper for the Nexora DRF API (/api/v1/...).
 * No build step / framework - plain browser JS, loaded as a classic
 * script so it exposes a single global: `Api`.
 */
(function (window) {
  "use strict";

  var API_ROOT = "/api/v1/";

  function getCookie(name) {
    var match = document.cookie.match(
      new RegExp("(^|;\\s*)" + name + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[2]) : null;
  }

  function buildUrl(path, params) {
    var url = path.indexOf("http") === 0 ? path : API_ROOT + path.replace(/^\/+/, "");
    if (params) {
      var parts = [];
      Object.keys(params).forEach(function (key) {
        var value = params[key];
        if (value === undefined || value === null || value === "") return;
        var values = Array.isArray(value) ? value : [value];
        values.forEach(function (v) {
          if (v === undefined || v === null || v === "") return;
          parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(v));
        });
      });
      var query = parts.join("&");
      if (query) {
        url += (url.indexOf("?") === -1 ? "?" : "&") + query;
      }
    }
    return url;
  }

  function request(method, path, body, params) {
    var options = {
      method: method,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    };

    var isForm = typeof FormData !== "undefined" && body instanceof FormData;

    if (["POST", "PUT", "PATCH", "DELETE"].indexOf(method) !== -1) {
      options.headers["X-CSRFToken"] = getCookie("csrftoken");
    }

    if (body !== undefined && body !== null) {
      if (isForm) {
        options.body = body;
      } else {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
      }
    }

    return fetch(buildUrl(path, params), options).then(function (response) {
      if (response.status === 204) {
        return null;
      }
      return response
        .json()
        .catch(function () {
          return null;
        })
        .then(function (data) {
          if (!response.ok) {
            var error = new Error(
              (data && (data.detail || summarizeErrors(data))) ||
                "Request failed (" + response.status + ")"
            );
            error.status = response.status;
            error.data = data;
            throw error;
          }
          return data;
        });
    });
  }

  function summarizeErrors(data) {
    if (typeof data !== "object" || data === null) return null;
    var parts = [];
    Object.keys(data).forEach(function (key) {
      var value = data[key];
      var text = Array.isArray(value) ? value.join(" ") : String(value);
      parts.push(key === "non_field_errors" ? text : key + ": " + text);
    });
    return parts.join(" ");
  }

  window.Api = {
    get: function (path, params) {
      return request("GET", path, null, params);
    },
    post: function (path, body) {
      return request("POST", path, body || {});
    },
    patch: function (path, body) {
      return request("PATCH", path, body || {});
    },
    put: function (path, body) {
      return request("PUT", path, body || {});
    },
    delete: function (path) {
      return request("DELETE", path);
    },
  };
})(window);
