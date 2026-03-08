import os
import csv

def clean_and_validate_file(file_path):
    # Convert TRUE/FALSE to true/false for JSON compatibility, remove NULL, and empty JSON objects/arrays
    # Also remove quotes around values that might come from bad CSV exports, but be careful not to break valid JSON strings
    forbidden_patterns = {
        'NULL': '',
        'null': '',
        '{}': '',
        '[]': '',
        '"[': '[', # Remove leading quote for JSON array
        ']"': ']', # Remove trailing quote for JSON array
        '"{': '{', # Remove leading quote for JSON object
        '}"': '}', # Remove trailing quote for JSON object
        '","': ',', # Replace quoted comma with simple comma
    }
    
    found_issues_in_file = False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    for pattern, replacement in forbidden_patterns.items():
        content = content.replace(pattern, replacement)
    
    if original_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cleaned and updated {file_path}")
        found_issues_in_file = True # Mark as issue found if content was modified

    # After cleaning, re-check for any remaining *critical* forbidden patterns for validation
    # These are patterns that should absolutely not be present and indicate a deeper issue
    critical_forbidden_patterns = ['null', 'NULL'] # Re-check for original patterns

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            for j, field in enumerate(row):
                for pattern in critical_forbidden_patterns:
                    if pattern in field:
                        print(f"Found critical forbidden pattern '{pattern}' in {file_path} at row {i+1}, column {j+1} AFTER cleaning")
                        found_issues_in_file = True
    return found_issues_in_file

def validate_files():
    total_issues_found = False
    for root, dirs, files in os.walk('listings/specific-networks/solana'):
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