import csv
import os

def count_cells(filepath, target_cols=None):
    if not os.path.exists(filepath):
        return 0, 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_cells = 0
        row_count = 0
        for row in reader:
            row_count += 1
            for k, v in row.items():
                # If target_cols is specified, only count those
                if target_cols and k not in target_cols:
                    continue
                
                # Check for non-null
                if v and v.strip() and v.lower() != 'null':
                    total_cells += 1
        return total_cells, row_count

# PR #453: TON devTool.csv
ton_cells, ton_rows = count_cells('chain-love/networks/ton/devTool.csv')

# PR #456: Global Providers (Enrichment)
# We assume the "enrichment" targets specific columns related to Audits/SLAs
# Based on file header: uptimeSla, bandwidthSla, blocksBehindSla, supportSla, verifiedUptime, verifiedLatency, verifiedBlocksBehindAvg
sla_cols = [
    'uptimeSla', 'bandwidthSla', 'blocksBehindSla', 'supportSla',
    'verifiedUptime', 'verifiedLatency', 'verifiedBlocksBehindAvg',
    'securityImprovements', 'monitoringAndAnalytics' # seemingly related to "audits" / quality
]
provider_cells, provider_rows = count_cells('chain-love/providers/api.csv', target_cols=sla_cols)

print(f"PR #453 (TON devTool): {ton_cells} non-null cells across {ton_rows} rows.")
print(f"PR #456 (Providers SLA/Audit): {provider_cells} non-null cells in SLA/Audit columns.")
