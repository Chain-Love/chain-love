import csv
import os

def deduplicate_network_files(network_name):
    print(f"Deduplicating network: {network_name}")
    # Try both current dir and 'chain-love' dir
    if os.path.exists("networks"):
        base_dir = "."
    elif os.path.exists("chain-love/networks"):
        base_dir = "chain-love"
    else:
        print("Could not find networks directory.")
        return
        
    network_dir = os.path.join(base_dir, "networks", network_name)
    providers_dir = os.path.join(base_dir, "providers")
    
    if not os.path.exists(network_dir):
        print(f"Network directory {network_dir} does not exist.")
        return

    # Map category names to their provider files
    category_to_provider = {
        "api.csv": "api.csv",
        "bridge.csv": "bridge.csv",
        "devTool.csv": "devTool.csv",
        "explorer.csv": "explorer.csv",
        "faucet.csv": "faucet.csv",
        "oracle.csv": "oracle.csv",
        "wallet.csv": "wallet.csv",
        "analytic.csv": "analytic.csv"
    }

    # Load global providers
    providers_data = {}
    for cat_file in category_to_provider.values():
        provider_path = os.path.join(providers_dir, cat_file)
        if os.path.exists(provider_path):
            with open(provider_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                providers_data[cat_file] = {row['slug']: row for row in reader}

    # Process each file in the network directory
    for file_name in os.listdir(network_dir):
        if file_name.lower() not in [k.lower() for k in category_to_provider.keys()]:
            continue

        network_file_path = os.path.join(network_dir, file_name)
        
        # Match case-insensitive for the category
        provider_cat = None
        for k, v in category_to_provider.items():
            if k.lower() == file_name.lower():
                provider_cat = v
                break
        
        if not provider_cat or provider_cat not in providers_data:
            continue

        global_providers = providers_data[provider_cat]
        
        updated_rows = []
        headers = []
        
        if not os.path.exists(network_file_path):
            continue

        with open(network_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if not headers:
                continue
            for row in reader:
                provider_ref = row.get('provider', '')
                if provider_ref and provider_ref.startswith('!provider:'):
                    provider_slug = provider_ref.split(':', 1)[1]
                    if provider_slug in global_providers:
                        global_row = global_providers[provider_slug]
                        # Compare each field and clear if it matches global
                        for field in headers:
                            if field in ['slug', 'provider', 'chain']: # Keep these
                                continue
                            
                            # If the network cell matches the global cell, clear it
                            if field in global_row:
                                if str(row[field]) == str(global_row[field]):
                                    row[field] = ''
                updated_rows.append(row)

        if updated_rows:
            with open(network_file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(updated_rows)
            print(f"Updated {network_file_path}")

if __name__ == "__main__":
    import sys
    networks = sys.argv[1:] if len(sys.argv) > 1 else ["arbitrum", "ton", "bsc", "ethereum", "optimism", "polygon"]
    for network in networks:
        deduplicate_network_files(network)
