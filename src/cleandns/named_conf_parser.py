import re
import subprocess
from pathlib import Path

from cleandns.exceptions import NamedConfNotFoundError, NamedConfParseError

# Only zones of these types have a local file that can be edited.
_EDITABLE_TYPES = {"master", "primary"}

_ZONE_RE = re.compile(r'^\s*zone\s+"([^"]+)"')
_TYPE_RE = re.compile(r'^\s*type\s+(\w+)\s*;')
_FILE_RE = re.compile(r'^\s*file\s+"([^"]+)"\s*;')


class NamedConfParser:
    """
    Parses named-checkconf -p output to build a zone-name → file-path mapping.
    Only master/primary zones (i.e. zones with a locally editable file) are included.
    """

    @staticmethod
    def parse(text: str) -> dict[str, Path]:
        """
        Parse the output of `named-checkconf -p` and return a mapping of
        zone name to zone file path for all master/primary zones.
        """
        zones: dict[str, Path] = {}
        lines = text.splitlines()
        i = 0

        while i < len(lines):
            zone_match = _ZONE_RE.match(lines[i])

            if zone_match:
                zone_name = zone_match.group(1)
                zone_type: str | None = None
                zone_file: str | None = None

                # Depth starts at the brace count of the zone declaration line.
                depth = lines[i].count("{") - lines[i].count("}")
                i += 1

                # Scan until the zone block closes.
                while i < len(lines) and depth > 0:
                    line = lines[i]
                    depth += line.count("{") - line.count("}")

                    type_match = _TYPE_RE.match(line)
                    if type_match:
                        zone_type = type_match.group(1).lower()

                    file_match = _FILE_RE.match(line)
                    if file_match:
                        zone_file = file_match.group(1)

                    i += 1

                if zone_type in _EDITABLE_TYPES and zone_file is not None:
                    zones[zone_name] = Path(zone_file)
            else:
                i += 1

        return zones

    @classmethod
    def from_system(cls) -> dict[str, Path]:
        """
        Run `named-checkconf -p` and return the parsed zone mapping.
        Raises NamedConfNotFoundError if named-checkconf is not on PATH.
        Raises NamedConfParseError if named-checkconf exits with a non-zero status.
        """
        try:
            result = subprocess.run(
                ["named-checkconf", "-p"],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as e:
            raise NamedConfNotFoundError(
                "named-checkconf not found. Is BIND9 installed and on PATH?"
            ) from e
        except subprocess.CalledProcessError as e:
            raise NamedConfParseError(
                f"named-checkconf exited with an error:\n{e.stderr.strip()}"
            ) from e

        return cls.parse(result.stdout)
