import csv
import json
import os

def validate_json_cells(file_path):
    print(f"Validating JSON cells in: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            for col, value in row.items():
                if value and (value.startswith('[') or value.startswith('{')):
                    try:
                        json.loads(value)
                    except Exception as e:
                        print(f"  [ERROR] {file_path}: Line {i}, Column '{col}' has invalid JSON: {value}")
                        print(f"    Error: {e}")

def process_network(network):
    base_paths = [
        os.path.join("networks", network),
        os.path.join("chain-love", "networks", network)
    ]
    for path in base_paths:
        if os.path.exists(path):
            for file_name in os.listdir(path):
                if file_name.endswith('.csv'):
                    validate_json_cells(os.path.join(path, file_name))
            return

if __name__ == "__main__":
    process_network("ton")
    process_network("bsc")
