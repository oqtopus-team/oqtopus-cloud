LEN_VARCHAR = 255


class FormatError(Exception):
    """Custom exception for formatting errors"""

    def __init__(self, message_code: str, message_params: dict[str, str], message: str):
        super().__init__(message_code, message_params, message)
        self.message_code = message_code
        self.message_params = message_params
        self.message = message
