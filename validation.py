import os
import csv
import json

def clean_and_validate_file(file_path):
    # Convert TRUE/FALSE to true/false for JSON compatibility, remove NULL, and empty JSON objects/arrays
    # Also remove quotes around values that might come from bad CSV exports, but be careful not to break valid JSON strings
    forbidden_patterns = {
        'TRUE': 'true',
        'FALSE': 'false',
        'NULL': '',
        'null': '',
        '{}': '',
        '[]': '',
        '","': ',', # Replace quoted comma with simple comma
    }

    found_issues_in_file = False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"Processing {file_path} for cleaning.")
    original_content = content
    for pattern, replacement in forbidden_patterns.items():
        if pattern in content:
            print(f"  Replacing '{pattern}' with '{replacement}'.")
            content = content.replace(pattern, replacement)

    # Specific JSON cleanup for actionButtons
    if 'actionButtons' in content: # Simple check, can be more robust
        try:
            # Re-read content as CSV to target specific columns
            rows = []
            with open(file_path, 'r', encoding='utf-8') as f_csv:
                reader = csv.reader(f_csv)
                header = next(reader)
                rows.append(header)
                action_buttons_col_index = -1
                try:
                    action_buttons_col_index = header.index('actionButtons')
                except ValueError:
                    pass # Column not found, skip JSON processing

                for row_idx, row in enumerate(reader):
                    if action_buttons_col_index != -1 and len(row) > action_buttons_col_index:
                        cell_value = row[action_buttons_col_index]
                        if cell_value.strip().startswith('[') and cell_value.strip().endswith(']'):
                            try:
                                # Attempt to load and re-dump as JSON to clean up
                                cleaned_json = json.dumps(json.loads(cell_value.strip()))
                                if cleaned_json != cell_value.strip():
                                    print(f"  [JSON Clean] {file_path}: Line {row_idx+2}, Column 'actionButtons' cleaned.")
                                    row[action_buttons_col_index] = cleaned_json
                                    found_issues_in_file = True
                            except json.JSONDecodeError as e:
                                print(f"  [JSON Error] {file_path}: Line {row_idx+2}, Column 'actionButtons' has malformed JSON: {cell_value.strip()} - {e}")
                                # Attempt a more aggressive cleanup if simple JSON.loads fails
                                cleaned_cell = cell_value.strip().replace('""', '"') # Replace doubled quotes
                                try:
                                    cleaned_json = json.dumps(json.loads(cleaned_cell))
                                    if cleaned_json != cell_value.strip():
                                        print(f"  [JSON Auto-Fix] {file_path}: Line {row_idx+2}, Column 'actionButtons' auto-fixed JSON.")
                                        row[action_buttons_col_index] = cleaned_json
                                        found_issues_in_file = True
                                except json.JSONDecodeError:
                                    pass # Still malformed, leave as is or manual fix required
                    rows.append(row)
            
            if found_issues_in_file:
                with open(file_path, 'w', encoding='utf-8', newline='') as f_csv_out:
                    writer = csv.writer(f_csv_out)
                    writer.writerows(rows)
                print(f"  [JSON Update] {file_path} updated after JSON cleaning.")
        except Exception as e:
            print(f"  [ERROR] {file_path}: Error during actionButtons JSON processing: {e}")

    # Check if any initial forbidden patterns were replaced or JSON was cleaned
    if original_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cleaned and updated {file_path}")
        found_issues_in_file = True # Mark as issue found if content was modified

    # After cleaning, re-read content if file was updated by JSON cleaning
    if found_issues_in_file:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

    # After all cleaning, re-check for any remaining *critical* forbidden patterns for validation
    # These are patterns that should absolutely not be present and indicate a deeper issue
    critical_forbidden_patterns = ['TRUE', 'FALSE', 'null', 'NULL'] # Re-check for original patterns
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            for j, field in enumerate(row):
                for pattern in critical_forbidden_patterns:
                    if pattern in field:
                        print(f"Found critical forbidden pattern '{pattern}' in {file_path} at row {i+1}, column {j+1} AFTER cleaning. Value: '{field}'")
                        found_issues_in_file = True
    return found_issues_in_file

def validate_files():
    total_issues_found = False
    for root, dirs, files in os.walk('listings/specific-networks/linea'): # Assuming 'repo' is the base directory for CSVs
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                if clean_and_validate_file(file_path):
                    total_issues_found = True

    if not total_issues_found:
        print("Validation successful: No critical forbidden patterns found in any .csv files.")
    else:
        print("Validation complete: Some critical forbidden patterns were found. Please review the output.")

if __name__ == '__main__':
    validate_files()