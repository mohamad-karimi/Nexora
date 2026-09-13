(function (window, document) {
  "use strict";

  function showError(form, message) {
    var box = form.querySelector(".js-form-error");
    if (!box) return;
    box.textContent = message;
    box.style.display = message ? "" : "none";
  }

  function getNextUrl() {
    var params = new URLSearchParams(window.location.search);
    return params.get("next") || "/account/";
  }

  function wireLogin() {
    var form = document.getElementById("login-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");
      var username = document.getElementById("login-username").value.trim();
      var password = document.getElementById("login-password").value;

      window.Api.post("auth/login/", { username: username, password: password })
        .then(function () {
          window.location.href = getNextUrl();
        })
        .catch(function (error) {
          showError(form, error.message || "Login failed. Please try again.");
        });
    });
  }

  function wireRegister() {
    var form = document.getElementById("register-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");

      var password = document.getElementById("register-password").value;
      var passwordConfirm = document.getElementById("register-password-confirm").value;
      if (password !== passwordConfirm) {
        showError(form, "Passwords do not match.");
        return;
      }

      var termsCheckbox = form.querySelector('input[name="checkbox"]');
      if (termsCheckbox && !termsCheckbox.checked) {
        showError(form, "You must agree to the Terms & Policy to register.");
        return;
      }

      var accountTypeInput = form.querySelector('input[name="account_type"]:checked');

      var payload = {
        username: document.getElementById("register-username").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: password,
        security_code: document.getElementById("register-security-code").value.trim(),
        account_type: accountTypeInput ? accountTypeInput.value : "customer",
        agree_terms: !!(termsCheckbox && termsCheckbox.checked),
      };

      window.Api.post("auth/register/", payload)
        .then(function () {
          window.location.href = "/account/";
        })
        .catch(function (error) {
          showError(form, error.message || "Registration failed. Please try again.");
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireLogin();
    wireRegister();
  });
})(window, document);
