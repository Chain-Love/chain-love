import csv
import os

def fix_csv_column_counts(directory):
    print(f"Fixing CSV files in: {directory}")
    if not os.path.exists(directory):
        return

    for file_name in os.listdir(directory):
        if not file_name.endswith('.csv'):
            continue
            
        file_path = os.path.join(directory, file_name)
        updated_rows = []
        header = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # We use a custom reader to avoid automatic parsing issues with extra columns
            # but standard csv reader is usually fine for extra commas at the end
            reader = csv.reader(f)
            try:
                header = next(reader)
                num_cols = len(header)
                updated_rows.append(header)
                
                for i, row in enumerate(reader, start=2):
                    if len(row) > num_cols:
                        # Check if the extra columns are just empty
                        if all(c == '' for c in row[num_cols:]):
                            row = row[:num_cols]
                        else:
                            print(f"  [WARNING] {file_name}: Line {i} has data in extra columns: {row[num_cols:]}")
                            row = row[:num_cols]
                    elif len(row) < num_cols:
                        # Pad with empty strings
                        row = row + [''] * (num_cols - len(row))
                    updated_rows.append(row)
            except Exception as e:
                print(f"  [ERROR] {file_name}: {str(e)}")
                continue

        if updated_rows:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(updated_rows)
            print(f"  [FIXED] {file_name}")

if __name__ == "__main__":
    import sys
    # Handle paths relative to repo root
    if os.path.basename(os.getcwd()) == "chain-love":
        ton_dir = os.path.join("networks", "ton")
        bsc_dir = os.path.join("networks", "bsc")
    else:
        ton_dir = os.path.join("chain-love", "networks", "ton")
        bsc_dir = os.path.join("chain-love", "networks", "bsc")
        
    fix_csv_column_counts(ton_dir)
    fix_csv_column_counts(bsc_dir)