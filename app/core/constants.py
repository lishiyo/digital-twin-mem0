"""Application-wide constants."""

# Default mock user for development/testing
DEFAULT_USER_ID = "digital-twin-test-user"
DEFAULT_USER_NAME = "Digital Twin Test User"

# Default user object used when authentication is not provided
DEFAULT_USER = {
    "id": DEFAULT_USER_ID,
    "name": DEFAULT_USER_NAME
} 