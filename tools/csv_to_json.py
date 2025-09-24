import csv
import json
import os

PROVIDER_REF_PREFIX="!provider:"

def try_parse_json(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if (not value.startswith("[") and not value.endswith("]")) and (not value.startswith("{") and not value.endswith("}")):
        return value
    return json.loads(value)

def is_nullish(value: str) -> bool:
    return isinstance(value, str) and (value.strip().lower() == "null" or value.strip() == "")

def is_boolish(value: str) -> bool:
    return isinstance(value, str) and (value.strip().lower() == "true" or value.strip().lower() == "false")

def is_trueish(value: str) -> bool:
    return isinstance(value, str) and value.strip().lower() == "true"

def normalize(data_by_category: dict):
    result = {}
    errors = []
    for category, items in data_by_category.items():
        result[category] = []
        for item in items:
            new_item = {}
            for key, value in item.items():
                new_item[key] = value
                if is_nullish(value):
                    new_item[key] = None
                if is_boolish(value):
                    new_item[key] = is_trueish(value)
                try:
                    new_item[key] = try_parse_json(new_item[key])
                except Exception as e:
                    errors.append(f"Failed to parse value '{value}' for key '{key}' in category '{category}' as JSON: {e}")
            result[category].append(new_item)
    return result, errors

def load_csv_to_dict_list(file_path: str) -> list[dict]|None:
    if not os.path.exists(file_path):
        return None

    result = []
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            result.append(row)
    return result

def find_one_by_slug(dict_list: list[dict], slug: str) -> dict|None:
    for item in dict_list:
        if item['slug'] == slug:
            return item
    return None

def is_provider_ref(string: str) -> bool:
    return string.strip().startswith(PROVIDER_REF_PREFIX)

def get_ref_slug(string: str) -> str:
    return string.strip()[len(PROVIDER_REF_PREFIX):]

def override(item: dict, providers: list[dict]):
    if not is_provider_ref(item['provider']):
        # If the provider is not a reference, return the item unchanged
        return item
    
    provider_slug = get_ref_slug(item['provider'])
    provider = find_one_by_slug(providers, provider_slug)

    if provider is None:
        print(f"Failed to find provider with slug {provider_slug}")
        return item

    # Keys we never copy from the provider
    skipped_keys = {'slug'} 
    # Keys we always copy, even if item has a value 
    always_copy_keys = {'provider'}

    for key in item.keys():
        if key in skipped_keys:
            continue
        
        v = item.get(key)
        if key in always_copy_keys or (v is None or v.strip() == ""):
            if key not in provider:
                continue
            item[key] = provider[key]
        
    return item

def process_category(data_by_category: dict, network_data_file_path: str, provider_data_file_path: str, property_name: str) -> dict:
    network_data = load_csv_to_dict_list(network_data_file_path)
    if network_data is None:
        # No network data - skip adding this category
        print(f"Failed to load network data from {network_data_file_path}, skipping {property_name}")
        return data_by_category.copy()

    provider_data = load_csv_to_dict_list(provider_data_file_path)
    if provider_data is not None:
        # Run overrides
        processed_data = [override(item, provider_data) for item in network_data]
    else:
        # No overrides - use network data as-is
        print(f"Failed to load provider data from {provider_data_file_path}, using network data as-is")
        processed_data = network_data
    
    # Return a new dict containing all previous entries in `data_by_category`,
    # plus (or replacing) one entry with key = `property_name` and value = `processed_data`.
    return {**data_by_category, property_name: processed_data}

def main():
    if not os.path.exists('networks'):
        print("No 'networks' directory found")
        return

    for network_name in os.listdir('networks'):
        network_dir_full_path = os.path.join('networks', network_name)
        # We're not interested in anything that's not a directory
        if not os.path.isdir(network_dir_full_path):
            continue

        result = {}

        # Assumptions:
        # - Network-specific data is located at: os.path.join(network_dir_full_path, "<category>.csv")
        # - Provider-specific data is located at: "providers/<category>.csv"
        # - Category names match both the filename (without extension) and the dictionary key in the result
        categories = ['rpc', 'indexing', 'oracle', 'bridge', 'explorer', 'faucet', 'analytic', 'wallet', 'devTool']
        for category in categories:
            result = process_category(
                data_by_category=result,
                property_name=category,
                network_data_file_path=os.path.join(network_dir_full_path, f"{category}.csv"),
                provider_data_file_path=f"providers/{category}.csv",
            )

        result, errors = normalize(result)
        if len(errors) > 0:
            print(f"Errors while normalizing {network_name} JSON:")
            for error in errors:
                print(error)
            exit(1)

        os.makedirs('json', exist_ok=True)
        with(open(f"json/{network_name}.json", 'w+')) as f:
            json.dump(result, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
