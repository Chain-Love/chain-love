import csv
import os
import sys

def check_csv_validity(directory):
    print(f"Checking CSV files in: {os.path.abspath(directory)}")
    if not os.path.exists(directory):
        print(f"  [ERROR] Directory does not exist: {directory}")
        return False
        
    errors = []
    for file_name in os.listdir(directory):
        if not file_name.endswith('.csv'):
            continue
            
        file_path = os.path.join(directory, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                num_cols = len(headers)
                for i, row in enumerate(reader, start=2):
                    if len(row) != num_cols:
                        errors.append(f"{file_name}: Line {i} has {len(row)} columns, expected {num_cols}")
        except Exception as e:
            errors.append(f"{file_name}: Error reading file: {str(e)}")
            
    if errors:
        for error in errors:
            print(f"  [ERROR] {error}")
        return False
    else:
        print("  [OK] All CSVs are syntactically valid.")
        return True

if __name__ == "__main__":
    # If we are in the chain-love folder
    if os.path.basename(os.getcwd()) == "chain-love":
        ton_dir = os.path.join("networks", "ton")
        bsc_dir = os.path.join("networks", "bsc")
    else:
        ton_dir = os.path.join("chain-love", "networks", "ton")
        bsc_dir = os.path.join("chain-love", "networks", "bsc")
    
    valid_ton = check_csv_validity(ton_dir)
    valid_bsc = check_csv_validity(bsc_dir)
    
    if not (valid_ton and valid_bsc):
        sys.exit(1)
