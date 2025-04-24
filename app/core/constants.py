"""Application-wide constants."""

# Default mock user for development/testing
DEFAULT_USER_ID = "digital-twin-test-user-2"
DEFAULT_USER_NAME = "Digital Twin Test User 2"
DEFAULT_USER_EMAIL = "digital-twin-test-user-2@example.com"
# Default user object used when authentication is not provided
DEFAULT_USER = {
    "id": DEFAULT_USER_ID,
    "name": DEFAULT_USER_NAME,
    "email": DEFAULT_USER_EMAIL
} 