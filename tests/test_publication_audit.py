import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

AUDIT = Path(__file__).resolve().parents[1] / "tools/audit_public.py"


class PublicationTests(unittest.TestCase):
    def test_source_and_decoded_binary_key_are_checked_without_echoing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "public.txt").write_text("generic firmware\n")
            subprocess.run(["git", "-C", directory, "add", "public.txt"], check=True)
            private = root / "private"
            private.mkdir()
            secret = "PRIVATE_TEST_WIFI_PASSWORD"
            for file, obj in [("stock-connection.json", {"ssid": "TestNetwork", "passcode": secret}),
                              ("stock-info.json", {}), ("stock-config.json", {})]:
                (private / file).write_text(json.dumps(obj))
            key = bytes(range(1, 33))
            staged = private / "staged.json"
            staged.write_text(json.dumps({"records": [{"key": "88491486", "value_base64": base64.b64encode(key).decode()}]}))
            binary = private / "app.bin"
            binary.write_bytes(b"generic test image")
            command = [sys.executable, str(AUDIT), "--backup", str(private),
                       "--staged-settings", str(staged), "--binary", str(binary)]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            binary.write_bytes(b"image header" + key + b"tail")
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("staged-bytes:88491486", result.stdout)
            (root / "public.txt").write_text(secret)
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertIn("stock-connection.json:passcode", result.stdout)


if __name__ == "__main__":
    unittest.main()
