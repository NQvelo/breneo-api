"""Domain errors for resume ingestion, extraction, and matching."""


class ResumeReaderError(Exception):
    """Base error safe to return from the ATS API."""

    code = "resume_error"
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnsupportedResumeFormat(ResumeReaderError):
    code = "unsupported_format"
    status_code = 415


class CorruptResumeFile(ResumeReaderError):
    code = "corrupt_file"
    status_code = 400


class PasswordProtectedPDF(ResumeReaderError):
    code = "password_protected"
    status_code = 400


class EmptyResumeError(ResumeReaderError):
    code = "empty_resume"
    status_code = 422


class ResumeTooLarge(ResumeReaderError):
    code = "file_too_large"
    status_code = 413


class OCRUnavailable(ResumeReaderError):
    code = "ocr_unavailable"
    status_code = 422


class JobNotFound(ResumeReaderError):
    code = "job_not_found"
    status_code = 404


class JobDescriptionMissing(ResumeReaderError):
    code = "job_description_missing"
    status_code = 400


class AiUnavailable(ResumeReaderError):
    code = "ai_unavailable"
    status_code = 503


class IncompleteResumeError(ResumeReaderError):
    """The model response is missing one or more required CV fields."""

    code = "incomplete_resume"
    status_code = 422

    def __init__(self, missing: list[str]):
        self.missing = missing
        shown = ", ".join(missing[:12])
        if len(missing) > 12:
            shown = f"{shown} (+{len(missing) - 12} more)"
        super().__init__(f"The AI left required fields empty: {shown}")


class LlmNotConfigured(Exception):
    """No Groq or OpenAI key is available."""


class LlmExtractionFailed(Exception):
    """The model response could not be parsed into ResumeData."""
