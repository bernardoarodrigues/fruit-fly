import io
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from fruitfly.morphology import RangeReader, trace_lattice_spacing


class Response(io.BytesIO):
    def __init__(self, payload, status, content_range=None):
        super().__init__(payload)
        self.status = status
        self.headers = {"Content-Range": content_range}


class RangeReaderTests(unittest.TestCase):
    def test_zip_member_streamed_using_exact_ranges(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("test.txt", "verified male specimen metadata\n" * 100)
        payload = data.getvalue()
        requests = []

        def fetch(request, **kwargs):
            requested = request.headers["Range"]
            requests.append(requested)
            start, end = map(int, requested.removeprefix("bytes=").split("-"))
            return Response(payload[start:end + 1], 206, f"bytes {start}-{end}/{len(payload)}")

        with patch("urllib.request.urlopen", fetch):
            reader = RangeReader("https://example.test/archive.zip", len(payload))
            with zipfile.ZipFile(reader) as archive:
                self.assertEqual(archive.read("test.txt").decode(),
                                 "verified male specimen metadata\n" * 100)
        self.assertGreater(len(requests), 1)

    def test_no_range_fallback_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=Response(b"whole archive", 200)):
            with self.assertRaises(IOError):
                RangeReader("https://example.test/archive.zip", 100).read(10)

    def test_accidental_archive_read_stops_before_network(self):
        with patch("urllib.request.urlopen") as request:
            with self.assertRaises(ValueError):
                RangeReader("https://example.test/archive.zip", 148_000_000_000).read()
            request.assert_not_called()

    def test_trace_pitch_recovers_uniform_grid_and_rejects_inconsistent_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.swc"
            path.write_text("1 0 0.003 0.006 0.009 1 -1\n2 0 0.006 0.009 0.012 1 1\n")
            pitch, error = trace_lattice_spacing(path)
            self.assertAlmostEqual(pitch, .003)
            self.assertLess(error, 1e-10)
            path.write_text("1 0 0.0031 0.006 0.009 1 -1\n2 0 0.006 0.009 0.012 1 1\n")
            with self.assertRaises(ValueError):
                trace_lattice_spacing(path)


if __name__ == "__main__":
    unittest.main()
