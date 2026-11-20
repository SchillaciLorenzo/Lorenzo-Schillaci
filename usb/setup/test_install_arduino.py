"""Offline tests for the installer: no Internet, SDK installation or serial I/O.

Every run uses a temporary copy of the installer and an archive created by
this test. Only that copy receives the fixture's expected SHA-256; the pinned
production checksum is asserted and the production installer is never edited.
Real sha256sum and tar still verify/extract the test-owned fixture.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest


INSTALLER = Path(__file__).with_name("install_arduino.sh")
OFFICIAL_SHA256 = "2ed4e1436bb3be1265966af8eba95dd25e28f3a9f92d0a58d371ed14dbaf550f"
ARCHIVE_NAME = "arduino-cli_1.6.0_Linux_ARM64.tar.gz"
INDEX_URL = "https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"
FQBN = "esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M"


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hamda-installer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.root = self.sandbox / "build space $(touch SHELL_EXECUTED)"
        self.bin = self.sandbox / "fake-bin"
        self.bin.mkdir()
        self.events = self.sandbox / "events.jsonl"
        self.source = INSTALLER.read_text(encoding="utf-8")
        self.assertEqual(self.source.count(OFFICIAL_SHA256), 1)
        self.original_hash = hashlib.sha256(INSTALLER.read_bytes()).hexdigest()
        self.addCleanup(self.assert_production_untouched)
        self.fixture = self.sandbox / "fixture.tar.gz"
        self.make_fixture()
        self.script = self.sandbox / "installer-fixture.sh"
        fixture_hash = hashlib.sha256(self.fixture.read_bytes()).hexdigest()
        self.script.write_text(self.source.replace(OFFICIAL_SHA256, fixture_hash), encoding="utf-8")
        self.make_wrappers()

    def assert_production_untouched(self):
        self.assertEqual(hashlib.sha256(INSTALLER.read_bytes()).hexdigest(), self.original_hash)

    def write_program(self, path: Path, body: str):
        path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
        path.chmod(0o755)

    def make_fixture(self):
        body = f"#!{sys.executable}\n" + textwrap.dedent(
            """
            import json, os, pathlib, sys
            args = sys.argv[1:]
            event = {
                'kind': 'cli', 'argv': args,
                'directories': {key: os.environ.get('ARDUINO_DIRECTORIES_' + key.upper())
                                for key in ('data', 'downloads', 'user')},
                'home': os.environ.get('HOME'),
            }
            with open(os.environ['FAKE_EVENTS'], 'a', encoding='utf-8') as output:
                output.write(json.dumps(event) + '\\n')
            if len(args) < 2 or args[0] != '--config-file':
                print('Missing dedicated --config-file', file=sys.stderr)
                raise SystemExit(91)
            config = pathlib.Path(args[1])
            if not config.is_file():
                raise SystemExit(92)
            args = args[2:]
            command = ' '.join(args[:2]) if args and args[0] in ('core', 'board') else args[0]
            if os.environ.get('FAKE_FAIL_COMMAND') == command:
                print('simulated CLI failure: ' + command, file=sys.stderr)
                raise SystemExit(17)
            if any(word in args for word in ('upload', '--upload', '--port', 'monitor')):
                raise SystemExit(93)
            if args == ['version', '--format', 'json']:
                if os.environ.get('FAKE_BAD_VERSION_JSON'):
                    print('{not-json')
                else:
                    print(json.dumps({'VersionString': os.environ.get('FAKE_CLI_VERSION', '1.6.0')}))
            elif args[:2] in (['core', 'update-index'], ['core', 'install']):
                print('simulated ' + command)
            elif args == ['core', 'list', '--format', 'json']:
                field = os.environ.get('FAKE_INSTALLED_FIELD', 'installed_version')
                version = os.environ.get('FAKE_CORE_VERSION', '3.3.13')
                entry = {'id': 'esp32:esp32'}
                if field == 'both':
                    entry.update(installed=version, installed_version=version)
                elif field != 'missing':
                    entry[field] = version
                platforms = [entry]
                if os.environ.get('FAKE_DUPLICATE_CORE'):
                    platforms.append(dict(entry))
                print(json.dumps({'platforms': platforms}))
            elif args[:2] == ['board', 'details']:
                print('simulated board details')
            else:
                print('Unexpected CLI command: ' + repr(args), file=sys.stderr)
                raise SystemExit(94)
            """
        )
        encoded = body.encode("utf-8")
        with tarfile.open(self.fixture, "w:gz") as archive:
            member = tarfile.TarInfo("arduino-cli")
            member.size = len(encoded)
            member.mode = 0o755
            archive.addfile(member, io.BytesIO(encoded))

    def make_wrappers(self):
        self.write_program(self.bin / "uname", """
            import os, sys
            print(os.environ.get('FAKE_ARCH', 'aarch64') if sys.argv[1:] == ['-m']
                  else os.environ.get('FAKE_OS', 'Linux'))
        """)
        self.write_program(self.bin / "df", """
            import os
            print('Filesystem 1024-blocks Used Available Capacity Mounted on')
            print('/dev/fake 67108864 1048576 ' + os.environ.get('FAKE_FREE_KIB', '50331648') + ' 2% /')
        """)
        self.write_program(self.bin / "curl", """
            import json, os, pathlib, shutil, sys
            args = sys.argv[1:]
            with open(os.environ['FAKE_EVENTS'], 'a', encoding='utf-8') as output:
                output.write(json.dumps({'kind': 'curl', 'argv': args}) + '\\n')
            destination = pathlib.Path(args[args.index('--output') + 1])
            if os.environ.get('FAKE_CURL_FAIL'):
                destination.write_bytes(b'partial download')
                print('simulated curl transport error', file=sys.stderr)
                raise SystemExit(22)
            if os.environ.get('FAKE_BAD_ARCHIVE'):
                destination.write_bytes(b'not the expected archive')
            else:
                shutil.copyfile(os.environ['FAKE_ARCHIVE'], destination)
        """)

    def invoke(self, phase="--cli-only", *, path=None, **overrides):
        environment = os.environ.copy()
        original_home = environment.get("HOME")
        environment.update({
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "HAMDA_USB_BUILD_ROOT": str(self.root),
            "FAKE_EVENTS": str(self.events),
            "FAKE_ARCHIVE": str(self.fixture),
            # These pre-existing settings must not redirect CLI writes globally.
            "ARDUINO_DIRECTORIES_DATA": str(self.sandbox / "unwanted-global-data"),
            "ARDUINO_DIRECTORIES_USER": str(self.sandbox / "unwanted-global-user"),
        })
        environment.update(overrides)
        if path is not None:
            environment["PATH"] = path
        self.assertEqual(environment.get("HOME"), original_home)
        return subprocess.run(
            ["/bin/bash", str(self.script), phase],
            cwd=self.sandbox,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def recorded(self, kind=None):
        entries = [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []
        return [entry for entry in entries if kind is None or entry["kind"] == kind]

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_only_isolated_config_verified_archive_and_no_core_commands(self):
        self.assert_ok(self.invoke())
        config = json.loads((self.root / "arduino-cli.yaml").read_text())
        self.assertEqual(config, {
            "directories": {name: str(self.root / name) for name in ("data", "downloads", "user")},
            "board_manager": {"additional_urls": [INDEX_URL]},
        })
        cli = self.recorded("cli")
        self.assertEqual(len(cli), 1)
        self.assertEqual(cli[0]["argv"], ["--config-file", str(self.root / "arduino-cli.yaml"), "version", "--format", "json"])
        self.assertEqual(cli[0]["directories"], config["directories"])
        self.assertEqual(cli[0]["home"], os.environ.get("HOME"))
        self.assertTrue((self.root / ARCHIVE_NAME).is_file())
        self.assertFalse((self.root / (ARCHIVE_NAME + ".tmp")).exists())
        self.assertTrue(any((self.root / "logs").glob("cli-only.*")))
        curl = self.recorded("curl")[0]["argv"]
        for flag, value in (("--retry", "3"), ("--connect-timeout", "20"), ("--max-time", "300"), ("--proto", "=https"), ("--proto-redir", "=https")):
            self.assertEqual(curl[curl.index(flag) + 1], value)
        self.assertNotIn("--insecure", curl)
        self.assertIn("--fail", curl)
        self.assertEqual(curl[-1], "https://github.com/arduino/arduino-cli/releases/download/v1.6.0/" + ARCHIVE_NAME)

    def test_core_only_requires_previous_verified_cli(self):
        result = self.invoke("--core")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("eseguire prima --cli-only", result.stderr)
        self.assertEqual(self.recorded(), [])

    def test_core_accepts_exact_version_in_either_known_single_field(self):
        self.assert_ok(self.invoke())
        for field in ("installed_version", "installed"):
            with self.subTest(field=field):
                self.assert_ok(self.invoke("--core", FAKE_INSTALLED_FIELD=field))
        for entry in self.recorded("cli"):
            args = entry["argv"]
            self.assertEqual(args[:2], ["--config-file", str(self.root / "arduino-cli.yaml")])
            self.assertTrue(set(args).isdisjoint({"upload", "--upload", "--port", "monitor"}))
            if args[2:4] == ["core", "install"]:
                self.assertIn("esp32:esp32@3.3.13", args)
                self.assertIn("--skip-post-install", args)
                self.assertEqual(args[args.index("--additional-urls") + 1], INDEX_URL)
            if args[2:4] == ["board", "details"]:
                self.assertEqual(args[-2:], ["--fqbn", FQBN])

    def test_core_list_wrong_unknown_ambiguous_or_duplicate_metadata_fails_closed(self):
        self.assert_ok(self.invoke())
        scenarios = [
            {"FAKE_CORE_VERSION": "3.3.12"},
            {"FAKE_INSTALLED_FIELD": "missing"},
            {"FAKE_INSTALLED_FIELD": "latest_version"},
            {"FAKE_INSTALLED_FIELD": "both"},
            {"FAKE_DUPLICATE_CORE": "1"},
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                count_before = len(self.recorded("cli"))
                result = self.invoke("--core", **scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("CORE COMPLETATO", result.stdout)
                new_calls = self.recorded("cli")[count_before:]
                self.assertFalse(any(entry["argv"][2:4] == ["board", "details"] for entry in new_calls))

    def test_bad_cli_version_or_json_is_not_success(self):
        for scenario in ({"FAKE_CLI_VERSION": "1.5.0"}, {"FAKE_BAD_VERSION_JSON": "1"}):
            with self.subTest(scenario=scenario):
                result = self.invoke(**scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("CLI-ONLY COMPLETATO", result.stdout)

    def test_wrong_architecture_or_os_refuses_before_download(self):
        for scenario in ({"FAKE_ARCH": "x86_64"}, {"FAKE_OS": "Darwin"}):
            with self.subTest(scenario=scenario):
                result = self.invoke(**scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.recorded(), [])

    def test_free_space_limit_is_eight_gib(self):
        result = self.invoke(FAKE_FREE_KIB=str(8 * 1024 * 1024 - 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("8 GiB", result.stderr)
        self.assertEqual(self.recorded(), [])
        self.assert_ok(self.invoke(FAKE_FREE_KIB=str(8 * 1024 * 1024)))

    def test_missing_checksum_tool_refuses_before_download(self):
        isolated = self.sandbox / "limited-path"
        isolated.mkdir()
        for name in ("uname", "df", "python3", "curl"):
            target = self.bin / name if (self.bin / name).exists() else Path(shutil.which(name))
            (isolated / name).symlink_to(target)
        result = self.invoke(path=str(isolated))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Strumento essenziale assente: sha256sum", result.stderr)
        self.assertEqual(self.recorded(), [])

    def test_bad_archive_hash_prevents_extraction_and_cli_execution(self):
        result = self.invoke(FAKE_BAD_ARCHIVE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recorded("cli"), [])
        self.assertFalse((self.root / "tools" / "arduino-cli").exists())
        self.assertFalse((self.root / ARCHIVE_NAME).exists())
        self.assertTrue((self.root / (ARCHIVE_NAME + ".tmp")).exists())

    def test_transport_failure_exit_status_is_preserved(self):
        result = self.invoke(FAKE_CURL_FAIL="1")
        self.assertEqual(result.returncode, 22)
        self.assertIn("simulated curl transport error", result.stdout + result.stderr)
        self.assertNotIn("CLI-ONLY COMPLETATO", result.stdout)
        self.assertEqual(self.recorded("cli"), [])

    def test_cli_command_errors_are_not_hidden_by_logging(self):
        self.assertEqual(self.invoke(FAKE_FAIL_COMMAND="version").returncode, 17)
        self.assert_ok(self.invoke())
        for command in ("core update-index", "core install", "core list", "board details"):
            with self.subTest(command=command):
                result = self.invoke("--core", FAKE_FAIL_COMMAND=command)
                self.assertEqual(result.returncode, 17)
                self.assertIn("simulated CLI failure", result.stdout + result.stderr)
                self.assertNotIn("CORE COMPLETATO", result.stdout)

    def test_rerun_preserves_cache_and_accepts_equivalent_json_formatting(self):
        self.assert_ok(self.invoke())
        archive = self.root / ARCHIVE_NAME
        before = archive.stat().st_mtime_ns
        config_path = self.root / "arduino-cli.yaml"
        equivalent = json.dumps(json.loads(config_path.read_text()), separators=(",", ":"))
        config_path.write_text(equivalent)
        self.assert_ok(self.invoke(FAKE_CURL_FAIL="1"))
        self.assertEqual(archive.stat().st_mtime_ns, before)
        self.assertEqual(len(self.recorded("curl")), 1)
        self.assertEqual(config_path.read_text(), equivalent)

    def test_paths_are_literal_and_conflicting_config_is_preserved(self):
        self.assert_ok(self.invoke())
        self.assertFalse((self.sandbox / "SHELL_EXECUTED").exists())
        self.assertFalse((self.sandbox / "unwanted-global-data").exists())
        self.assertFalse((self.sandbox / "unwanted-global-user").exists())
        config_path = self.root / "arduino-cli.yaml"
        changed = json.loads(config_path.read_text())
        changed["directories"]["data"] = "/unwanted/global"
        stored = json.dumps(changed)
        config_path.write_text(stored)
        count_before = len(self.recorded())
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conservata", result.stdout + result.stderr)
        self.assertEqual(config_path.read_text(), stored)
        self.assertEqual(len(self.recorded()), count_before)

    def test_tampered_cli_is_rejected_before_execution_in_core_phase(self):
        self.assert_ok(self.invoke())
        executable = self.root / "tools" / "arduino-cli"
        executable.write_text("#!/bin/sh\nexit 99\n")
        count_before = len(self.recorded("cli"))
        result = self.invoke("--core")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non coincide", result.stderr)
        self.assertEqual(len(self.recorded("cli")), count_before)


if __name__ == "__main__":
    unittest.main()
