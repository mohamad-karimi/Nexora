"""
drf-spectacular does not know about rest_framework_simplejwt.authentication
.JWTAuthentication out of the box, so without this it would be missing
from the generated OpenAPI schema's security schemes and the Swagger UI
"Authorize" dialog would have nowhere to accept a Bearer token.

This module only needs to be imported once, anywhere, before the schema
is generated -- see api.apps.ApiConfig.ready().
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SimpleJWTScheme(OpenApiAuthenticationExtension):
    target_class = "rest_framework_simplejwt.authentication.JWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "A JWT access token obtained from POST /api/v1/auth/token/. "
                "Enter just the token (no 'Bearer ' prefix)."
            ),
        }
