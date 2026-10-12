class BrainError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code
