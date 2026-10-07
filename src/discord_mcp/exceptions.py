class NotSupportedProtocolError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ToolNotFoundError(Exception):
    def __init__(self, tool_name):
        super().__init__("Tool not found")
        self.tool_name = tool_name


class MissingProtocolVersionError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ToolExecutionError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
