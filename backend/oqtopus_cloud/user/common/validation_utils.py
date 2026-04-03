LEN_VARCHAR = 255
FIELD_REQUIRED_MESSAGE = "{} is required."
FIELD_TOO_LONG_MESSAGE = (
    "The length of {} exceeds the limit. Please enter within {} characters"
)


class FormatError(Exception):
    """Custom exception for formatting errors"""

    pass
