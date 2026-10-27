"""证据校验拒绝携带可定位字段；不修改模型原文或放宽校验。"""
class MatterValidationError(ValueError):
    def __init__(self, code, path, reason):
        self.code = code
        self.path = path
        self.reason = reason
        super().__init__(reason)

    def detail(self, role, retry_count=0):
        return {"code": self.code, "role": role, "field_path": self.path,
                "reason": self.reason, "retry_count": retry_count}
