
class Result:
    def __init__(self, ok: bool, value=None, error=None):
        self.ok = ok
        self.value = value
        self.error = error

    @staticmethod
    def Ok(value=None):
        return Result(True, value=value)

    @staticmethod
    def Err(error):
        return Result(False, error=error)

    def __repr__(self):
        if self.ok:
            return f"Ok({self.value})"
        return f"Err({self.error})"