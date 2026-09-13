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

  // Simple human-check shown on the login form: a fresh random code is
  // rendered into the "security-code" digits and must be re-typed by
  // the user before the login request is sent. Not a substitute for a
  // real anti-bot/captcha service (the project has none), but it does
  // make the field an actually-validated check instead of a decorative
  // hardcoded number.
  function generateSecurityCode(form) {
    var code = "";
    for (var i = 0; i < 4; i++) {
      code += Math.floor(Math.random() * 10);
    }
    form.dataset.securityCode = code;
    var digits = form.querySelectorAll("#login-security-code-display b");
    digits.forEach(function (el, index) {
      el.textContent = code.charAt(index);
    });
    return code;
  }

  function wireLogin() {
    var form = document.getElementById("login-form");
    if (!form) return;

    generateSecurityCode(form);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");

      var username = document.getElementById("login-username").value.trim();
      var password = document.getElementById("login-password").value;
      var securityCodeInput = document.getElementById("login-security-code");
      var enteredCode = securityCodeInput ? securityCodeInput.value.trim() : "";
      var rememberMeInput = document.getElementById("login-remember");

      if (enteredCode !== form.dataset.securityCode) {
        showError(form, "Security code is incorrect. Please try again.");
        if (securityCodeInput) securityCodeInput.value = "";
        generateSecurityCode(form);
        return;
      }

      window.Api.post("auth/login/", {
        username: username,
        password: password,
        remember_me: !!(rememberMeInput && rememberMeInput.checked),
      })
        .then(function () {
          window.location.href = getNextUrl();
        })
        .catch(function (error) {
          showError(form, error.message || "Login failed. Please try again.");
          if (securityCodeInput) securityCodeInput.value = "";
          generateSecurityCode(form);
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

      var payload = {
        username: document.getElementById("register-username").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: password,
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
