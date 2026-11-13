#!/usr/bin/env python3
"""Check tracked source and optional binaries for KNOWN private values.

Requires PyYAML only when --secrets-yaml is used (present in the pinned builder).
This is a publication aid, not proof that every possible secret was identified.
Only field names and file paths are reported; secret values are never printed.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--secrets-yaml", type=Path)
    parser.add_argument("--staged-settings", type=Path)
    parser.add_argument("--binary", type=Path, action="append", default=[])
    args = parser.parse_args()
    values = {}

    def add(label, value):
        if isinstance(value, str) and len(value) >= 4:
            values[label] = value.encode()

    for filename, fields in [
        ("stock-connection.json", ["ssid", "passcode", "eap-username", "eap-identity", "eap-passcode"]),
        ("stock-config.json", ["host", "mqtt-host", "mqtt-username", "mqtt-password", "mqtt-topic", "auth-user", "auth-pass"]),
        ("stock-info.json", ["mac"]),
    ]:
        obj = json.loads((args.backup / filename).read_text())
        for key in fields:
            add(filename + ":" + key, obj.get(key))
        if filename == "stock-info.json" and obj.get("mac"):
            add("mac-no-colons", obj["mac"].replace(":", "").lower())
            values["mac-bytes"] = bytes.fromhex(obj["mac"].replace(":", ""))
    if args.secrets_yaml:
        import yaml
        for key, value in yaml.safe_load(args.secrets_yaml.read_text()).items():
            add("local:" + key, value)
            if "key" in key:
                try:
                    values["decoded:" + key] = base64.b64decode(value, validate=True)
                except (ValueError, TypeError):
                    pass
    if args.staged_settings:
        for record in json.loads(args.staged_settings.read_text())["records"]:
            if record.get("value_base64"):
                add("staged-text:" + record["key"], record["value_base64"])
                values["staged-bytes:" + record["key"]] = base64.b64decode(record["value_base64"])
    files = [Path(p) for p in subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0") if p]
    failures = []
    for path in files:
        if str(path).startswith(("private/", ".esphome")) or path.name == "secrets.yaml" or path.suffix in (".bin", ".elf", ".map"):
            failures.append((path, "forbidden tracked artifact"))
    for path in files + args.binary:
        data = path.read_bytes()
        for label, value in values.items():
            if value and value in data:
                failures.append((path, label))
    for path, label in failures:
        print("MATCH:", path, label)
    print(f"Scanned {len(files)} tracked files, {len(args.binary)} binaries, {len(values)} private patterns; {len(failures)} matches")
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
