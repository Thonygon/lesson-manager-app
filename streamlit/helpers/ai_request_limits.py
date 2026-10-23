"""Shared limits for external model responses in the Streamlit beta."""

TEXT_TIMEOUT_MS = 30_000
IMAGE_TIMEOUT_MS = 45_000
MAX_TEXT_OUTPUT_TOKENS = 16_384
MAX_TEXT_RESPONSE_BYTES = 512 * 1024
MAX_IMAGE_RESPONSE_BYTES = 12 * 1024 * 1024


def bounded_ai_text(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_TEXT_RESPONSE_BYTES:
        raise ValueError("AI provider text response exceeded the size limit")
    return value


def bounded_ai_image_data_url(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_IMAGE_RESPONSE_BYTES:
        raise ValueError("AI provider image response exceeded the size limit")
    return value


def read_bounded_ai_image(response) -> bytes:
    data = response.read(MAX_IMAGE_RESPONSE_BYTES + 1)
    if len(data) > MAX_IMAGE_RESPONSE_BYTES:
        raise ValueError("AI provider image response exceeded the size limit")
    return data
