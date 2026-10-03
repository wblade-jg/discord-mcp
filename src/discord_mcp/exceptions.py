class NotSupportedProtocolError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class MissingProtocolVersionError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

