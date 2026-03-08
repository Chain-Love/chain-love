import csv
import os

def fix_csv(file_path):
    print(f"Processing: {file_path}")
    rows = []
    header = None
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            rows.append(header)
            num_cols = len(header)
            for row in reader:
                # Truncate or pad
                if len(row) > num_cols:
                    row = row[:num_cols]
                elif len(row) < num_cols:
                    row = row + [''] * (num_cols - len(row))
                rows.append(row)
        except Exception as e:
            print(f"  Error: {e}")
            return

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"  Saved {len(rows)} rows with {len(header)} columns.")

def process_network(network):
    # Try to find the network directory
    base_paths = [
        os.path.join("networks", network),
        os.path.join("chain-love", "networks", network)
    ]
    for path in base_paths:
        if os.path.exists(path):
            for file_name in os.listdir(path):
                if file_name.endswith('.csv'):
                    fix_csv(os.path.join(path, file_name))
            return
    print(f"Network {network} not found.")

if __name__ == "__main__":
    process_network("ton")
    process_network("bsc")