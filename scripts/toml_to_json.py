import tomllib  # Built-in in Python 3.11+, use 'tomli' for older versions
import json
import sys
from pathlib import Path

def toml_to_json(toml_path, json_path=None):
    try:
        # Validate file existence
        file_path = Path(toml_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"TOML file not found: {toml_path}")

        # Read TOML file
        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        # Convert to JSON string
        json_data = json.dumps(data, indent=4)

        # Output to file or stdout
        if json_path:
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(json_data)
            print(f"✅ JSON saved to {json_path}")
        else:
            print(json_data)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python toml_to_json.py <input.toml> [output.json]")
        sys.exit(1)

    toml_file = sys.argv[1]
    json_file = sys.argv[2] if len(sys.argv) > 2 else None
    toml_to_json(toml_file, json_file)
