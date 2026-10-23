import unittest
from io import BytesIO
from unittest.mock import patch

from helpers import ai_request_limits as limits


class AiRequestLimitsTests(unittest.TestCase):
    def test_text_limit_counts_utf8_bytes(self):
        with patch.object(limits, "MAX_TEXT_RESPONSE_BYTES", 4):
            self.assertEqual(limits.bounded_ai_text("éé"), "éé")
            with self.assertRaisesRegex(ValueError, "size limit"):
                limits.bounded_ai_text("ééé")

    def test_image_limit_applies_to_data_url_and_stream(self):
        with patch.object(limits, "MAX_IMAGE_RESPONSE_BYTES", 16):
            self.assertEqual(limits.bounded_ai_image_data_url("data:image/png"), "data:image/png")
            with self.assertRaisesRegex(ValueError, "size limit"):
                limits.bounded_ai_image_data_url("data:image/png;base64,large")
            self.assertEqual(limits.read_bounded_ai_image(BytesIO(b"a" * 16)), b"a" * 16)
            with self.assertRaisesRegex(ValueError, "size limit"):
                limits.read_bounded_ai_image(BytesIO(b"a" * 17))


if __name__ == "__main__":
    unittest.main()
