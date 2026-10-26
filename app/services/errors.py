"""Lỗi có thể hiển thị trực tiếp, rõ nghĩa cho người dùng cuối."""


class UserFacingError(RuntimeError):
    """An error whose message is safe and actionable in the Vietnamese UI."""


class DependencyUnavailable(UserFacingError):
    """A required local program, package, or local asset is missing."""


class OCRProcessingError(UserFacingError):
    """OCR could not safely read the selected images."""


class AudioProcessingError(UserFacingError):
    """Audio segments could not be combined into a downloadable MP3."""
