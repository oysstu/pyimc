

class AmbiguousKeyError(LookupError):
    def __init__(self, message, choices=None):
        super().__init__(message)
        self.choices = choices
