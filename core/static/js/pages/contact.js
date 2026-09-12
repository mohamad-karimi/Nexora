(function (window, document) {
  "use strict";

  function setMessage(el, text, isError) {
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("text-danger", !!isError);
    el.classList.toggle("text-success", !isError && !!text);
  }

  function showAlert(text, icon) {
    if (typeof window.Swal === "undefined") return;
    window.Swal.fire({
      text: text,
      icon: icon,
    });
  }

  function prefillFromProfile(form) {
    var user = window.Site && window.Site.getUser && window.Site.getUser();
    if (!user) return;

    var profile = user.profile || {};
    var nameInput = form.querySelector('[name="name"]');
    var emailInput = form.querySelector('[name="email"]');
    var phoneInput = form.querySelector('[name="telephone"]');

    if (nameInput && !nameInput.value && profile.first_name) {
      nameInput.value = profile.first_name;
    }
    if (emailInput && !emailInput.value && user.email) {
      emailInput.value = user.email;
    }
    if (phoneInput && !phoneInput.value && profile.phone) {
      phoneInput.value = profile.phone;
    }
  }

  function wireContactForm() {
    var form = document.getElementById("contact-form");
    if (!form) return;

    var messageEl = form.parentElement.querySelector(".form-messege");
    var submitBtn = form.querySelector('button[type="submit"]');

    if (window.Site && window.Site.ready) {
      window.Site.ready().then(function () {
        prefillFromProfile(form);
      });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setMessage(messageEl, "", false);

      var payload = {
        name: form.querySelector('[name="name"]').value.trim(),
        email: form.querySelector('[name="email"]').value.trim(),
        phone: form.querySelector('[name="telephone"]').value.trim(),
        subject: form.querySelector('[name="subject"]').value.trim(),
        message: form.querySelector('[name="message"]').value.trim(),
      };

      if (submitBtn) submitBtn.disabled = true;

      window.Api.post("contact/", payload)
        .then(function () {
          form.reset();
          setMessage(messageEl, "Thanks! Your message has been sent.", false);
          showAlert("Your message has been sent successfully.", "success");
        })
        .catch(function (error) {
          var errorText =
            error.message || "Could not send your message. Please try again.";
          setMessage(messageEl, errorText, true);
          showAlert(errorText, "error");
        })
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  }

  document.addEventListener("DOMContentLoaded", wireContactForm);
})(window, document);
