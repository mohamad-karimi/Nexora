SECURITY_CODE_SESSION_KEY = "register_security_code"
LOGIN_SECURITY_CODE_SESSION_KEY = "login_security_code"

# JWT purposes / expirations for the email-verification and password-reset
# links. Kept as constants so accounts/tokens.py and accounts/emails.py stay
# in sync.
EMAIL_VERIFY_TOKEN_PURPOSE = "email_verify"
EMAIL_VERIFY_TOKEN_EXP_MINUTES = 60 * 24  # 24 hours
PASSWORD_RESET_TOKEN_PURPOSE = "password_reset"
PASSWORD_RESET_TOKEN_EXP_MINUTES = 30
