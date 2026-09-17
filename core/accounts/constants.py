SECURITY_CODE_SESSION_KEY = "register_security_code"
LOGIN_SECURITY_CODE_SESSION_KEY = "login_security_code"

# JWT purpose / expiration for the password-reset link. Kept as a constant
# so accounts/tokens.py and accounts/emails.py stay in sync. (The old
# email-verification JWT link has been replaced by the 6-digit OTP flow
# below -- see EMAIL_OTP_* / EMAIL_VERIFICATION_SESSION_KEY.)
PASSWORD_RESET_TOKEN_PURPOSE = "password_reset"
PASSWORD_RESET_TOKEN_EXP_MINUTES = 30

# Email-verification OTP. The session key holds only the pending user's
# primary key -- never anything the client can read or edit -- so the
# verify/resend endpoints always act on the user this *server-side*
# session was issued for, regardless of what a request body claims.
EMAIL_VERIFICATION_SESSION_KEY = "pending_email_verification_user_id"
EMAIL_OTP_LENGTH = 6
EMAIL_OTP_EXP_MINUTES = 10
EMAIL_OTP_MAX_ATTEMPTS = 5
EMAIL_OTP_RESEND_COOLDOWN_SECONDS = 60
