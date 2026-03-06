import os
import csv

def deduplicate_base_network_file(network_file_path):
    filename = os.path.basename(network_file_path)
    global_provider_file_path = os.path.join('repo', 'providers', filename)

    if not os.path.exists(global_provider_file_path):
        print(f"Warning: Global provider file not found for {filename}. Skipping deduplication.")
        return

    with open(network_file_path, 'r', encoding='utf-8') as f:
        network_content_lines = list(csv.reader(f))

    with open(global_provider_file_path, 'r', encoding='utf-8') as f:
        global_content_lines = list(csv.reader(f))

    original_network_header = network_content_lines[0]
    global_header = global_content_lines[0]

    # --- Advanced Header Alignment Logic ---
    # Create a mapping from global header column name to its index in the original network header
    # This handles missing columns in network_header and extra columns in network_header
    original_network_header_map = {col: i for i, col in enumerate(original_network_header)}
    
    # Create the new aligned network content (header + data rows)
    aligned_network_content = []
    aligned_network_header = []
    column_indices_to_keep = []

    for global_col in global_header:
        aligned_network_header.append(global_col)
        if global_col in original_network_header_map:
            column_indices_to_keep.append(original_network_header_map[global_col])
        else:
            # This means a column from global_header is missing in network_header
            # We'll handle this by adding an empty string in the data rows later
            column_indices_to_keep.append(None) # Placeholder to indicate a new column
    
    aligned_network_content.append(aligned_network_header)

    for original_network_row in network_content_lines[1:]:
        aligned_row = ['' for _ in aligned_network_header] # Initialize with empty strings
        for i, global_col in enumerate(aligned_network_header):
            original_index = -1
            if global_col in original_network_header_map:
                original_index = original_network_header_map[global_col]
            
            if original_index != -1 and original_index < len(original_network_row):
                aligned_row[i] = original_network_row[original_index]
        aligned_network_content.append(aligned_row)

    network_content_lines = aligned_network_content
    network_header = aligned_network_content[0]
    # --- End Advanced Header Alignment Logic ---

    if network_header != global_header:
        print(f"Error: Headers still do not match between {network_file_path} and {global_provider_file_path} after alignment. Aborting deduplication.")
        return

    modified_network_content = [network_header]
    header_to_index = {col: i for i, col in enumerate(network_header)}

    for i in range(1, len(network_content_lines)):
        network_row = list(network_content_lines[i])  # Create a mutable list
        provider_slug_col = network_row[header_to_index['provider']] if 'provider' in header_to_index else ''

        if provider_slug_col.startswith('!provider:'):
            provider_slug = provider_slug_col.split(':', 1)[1]

            global_provider_row = None
            for g_row in global_content_lines[1:]:
                if g_row and g_row[header_to_index['slug']] == provider_slug:
                    global_provider_row = g_row
                    break
            
            if global_provider_row:
                for j, cell_value in enumerate(network_row):
                    if j < len(global_provider_row) and cell_value == global_provider_row[j]:
                        network_row[j] = '' # Clear the cell if it's identical
        modified_network_content.append(network_row)
    
    with open(network_file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(modified_network_content)
    print(f"Deduplication complete for {network_file_path}")

def run_deduplication():
    base_network_dir = 'repo/networks/tezos'
    for root, dirs, files in os.walk(base_network_dir):
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                deduplicate_base_network_file(file_path)

if __name__ == '__main__':
    run_deduplication()
