import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RefreshExternalSignalsScriptTests(unittest.TestCase):
    def test_script_loads_env_local_and_sends_oddpool_header(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "fake-python"
            capture = tmp_path / "args.json"
            input_payload = tmp_path / "oddpool.json"
            input_payload.write_text(json.dumps({"arbitrages": []}))
            fake_bin.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "open(os.environ['CAPTURE'], 'w').write(json.dumps(sys.argv))\n"
            )
            fake_bin.chmod(0o755)
            env_path = root / ".env.local"
            old_env = env_path.read_text() if env_path.exists() else None
            try:
                env_path.write_text(
                    "ODDPOOL_API_KEY=test-key\n"
                    "ODDPOOL_API_URL=https://api.oddpool.com/arbitrage/current?min_net_cents=0.5\n"
                    "SOURCE=oddpool\n"
                    "PROXY=127.0.0.1:10808\n"
                )
                env = os.environ.copy()
                env.update(
                    {
                        "PYTHON_BIN": str(fake_bin),
                        "CAPTURE": str(capture),
                        "OUT": str(tmp_path / "external.ndjson"),
                        "REFRESH_WATCHLIST": "0",
                    }
                )

                subprocess.run(["bash", "scripts/refresh_external_signals.sh"], cwd=root, env=env, check=True, capture_output=True, text=True)
                argv = json.loads(capture.read_text())
            finally:
                if old_env is None:
                    env_path.unlink(missing_ok=True)
                else:
                    env_path.write_text(old_env)

        self.assertIn("--url", argv)
        self.assertIn("https://api.oddpool.com/arbitrage/current?min_net_cents=0.5", argv)
        self.assertIn("--header", argv)
        self.assertIn("X-API-Key=test-key", argv)
        self.assertIn("--proxy", argv)
        self.assertIn("127.0.0.1:10808", argv)


if __name__ == "__main__":
    unittest.main()
