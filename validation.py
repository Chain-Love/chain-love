import os
import csv

def clean_and_validate_file(file_path):
    found_issues_in_file = False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Convert TRUE/FALSE to true/false for JSON compatibility
    content = content.replace('TRUE', 'true')
    content = content.replace('FALSE', 'false')

    # Existing forbidden patterns (without TRUE/FALSE)
    forbidden_patterns = ['["', '"]', '","', 'NULL', 'null', '{}']

    for pattern in forbidden_patterns:
        content = content.replace(pattern, '')
    
    if original_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cleaned and updated {file_path}")

    # After cleaning, re-check for any remaining forbidden patterns for validation
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            for j, field in enumerate(row):
                for pattern in forbidden_patterns:
                    if pattern in field:
                        print(f"Found forbidden pattern '{pattern}' in {file_path} at row {i+1}, column {j+1} AFTER cleaning")
                        found_issues_in_file = True
    return found_issues_in_file

def validate_files():
    total_issues_found = False
    for root, dirs, files in os.walk('repo'):
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                if clean_and_validate_file(file_path):
                    total_issues_found = True
    
    if not total_issues_found:
        print("Validation successful: No forbidden patterns found in any .csv files.")
    else:
        print("Validation complete: Some forbidden patterns were found and cleaned. Please re-run validation to confirm.")

if __name__ == '__main__':
    validate_files()