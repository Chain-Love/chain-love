import csv
import os

def clean_value(val):
    val = val.strip()
    if val.lower() == 'null':
        return ''
    if val.lower() == 'true':
        return 'TRUE'
    if val.lower() == 'false':
        return 'FALSE'
    return val

def fix_file(file_path):
    # Rename if necessary
    if os.path.basename(file_path) == 'devtool.csv':
        new_path = os.path.join(os.path.dirname(file_path), 'devTool.csv')
        os.rename(file_path, new_path)
        file_path = new_path

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            num_cols = len(header)
            rows.append(header)
            for row in reader:
                # Clean values
                row = [clean_value(v) for v in row]
                # Normalize length
                if len(row) > num_cols:
                    row = row[:num_cols]
                elif len(row) < num_cols:
                    row = row + [''] * (num_cols - len(row))
                rows.append(row)
        except Exception as e:
            print(f"  Error fixing {file_path}: {e}")
            return

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"  Fixed: {file_path}")

def run_fix():
    for root, dirs, files in os.walk("."):
        if ".git" in root:
            continue
        for file in files:
            if file.endswith('.csv'):
                fix_file(os.path.join(root, file))

if __name__ == "__main__":
    run_fix()
