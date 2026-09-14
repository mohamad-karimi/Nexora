(function (window, document) {
  "use strict";

  function showError(form, message) {
    var box = form.querySelector(".js-form-error");
    if (!box) return;
    box.textContent = message;
    box.style.display = message ? "" : "none";
  }

  function showSuccess(form, message) {
    var box = form.querySelector(".js-form-success");
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

    var params = new URLSearchParams(window.location.search);
    if (params.get("verified")) {
      showSuccess(form, "Your email has been verified. You can now log in.");
    } else if (params.get("verify_error")) {
      showError(form, "That verification link is invalid or has expired.");
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");
      showSuccess(form, "");
      var username = document.getElementById("login-username").value.trim();
      var password = document.getElementById("login-password").value;
      var securityCode = document.getElementById("login-security-code").value.trim();

      window.Api.post("auth/login/", {
        username: username,
        password: password,
        security_code: securityCode,
      })
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

      var submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;

      window.Api.post("auth/register/", payload)
        .then(function () {
          // Registration doesn't log the user in and the account isn't
          // verified yet, so send them to the "check your email" page --
          // not /account/, which would just bounce them to login.
          window.location.href = "/email-verification-pending/";
        })
        .catch(function (error) {
          if (submitButton) submitButton.disabled = false;
          showError(form, error.message || "Registration failed. Please try again.");
        });
    });
  }

  function wireForgotPassword() {
    var form = document.getElementById("forgot-password-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");
      showSuccess(form, "");

      var email = document.getElementById("forgot-password-email").value.trim();

      window.Api.post("auth/forgot-password/", { email: email })
        .then(function (data) {
          form.reset();
          showSuccess(
            form,
            (data && data.detail) ||
              "If that email has an account, a reset link has been sent."
          );
        })
        .catch(function (error) {
          showError(form, error.message || "Something went wrong. Please try again.");
        });
    });
  }

  function wireResetPassword() {
    var form = document.getElementById("reset-password-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      showError(form, "");
      showSuccess(form, "");

      var newPassword = document.getElementById("reset-password-new").value;
      var confirmPassword = document.getElementById("reset-password-confirm").value;
      var token = document.getElementById("reset-password-token").value;

      if (newPassword !== confirmPassword) {
        showError(form, "Passwords do not match.");
        return;
      }

      window.Api.post("auth/reset-password/", {
        token: token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
        .then(function () {
          showSuccess(form, "Your password has been reset. Redirecting to login...");
          setTimeout(function () {
            window.location.href = "/login/";
          }, 1500);
        })
        .catch(function (error) {
          showError(form, error.message || "Could not reset your password. Please try again.");
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireLogin();
    wireRegister();
    wireForgotPassword();
    wireResetPassword();
  });
})(window, document);
