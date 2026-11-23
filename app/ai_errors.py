"""Actionable errors without echoing provider payloads, API keys or private inputs."""
class AIServiceError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def provider_error(status):
    messages = {
        400: ('invalid_request', 'Dữ liệu hoặc cấu hình model chưa hợp lệ. Hãy chạy Kiểm tra AI trong trang Admin.'),
        401: ('invalid_key', 'API key không hợp lệ. Kiểm tra lại key ở máy chủ.'),
        403: ('permission_denied', 'API key chưa có quyền dùng dịch vụ hoặc model này.'),
        404: ('model_unavailable', 'Không tìm thấy model hoặc tài khoản chưa được cấp quyền. Hãy kiểm tra tên model.'),
        429: ('quota_exceeded', 'Đã chạm hạn mức API. Chờ rồi thử lại hoặc kiểm tra hạn mức tài khoản.'),
        503: ('provider_unavailable', 'Dịch vụ AI đang bận. Vui lòng thử lại sau.'),
    }
    code, message = messages.get(status, ('provider_error', 'Dịch vụ AI chưa trả lời được. Hãy thử lại sau.'))
    return AIServiceError(code, message)
