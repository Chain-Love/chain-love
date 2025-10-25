import pandas as pd
import os
import glob

# Search recursively for .tsv files
tsv_files = glob.glob("**/*.tsv", recursive=True)

if not tsv_files:
    print("⚠️ No TSV files found in this folder or subfolders.")
else:
    print(f"📂 Found {len(tsv_files)} TSV file(s) to convert...\n")

    for tsv_file in tsv_files:
        try:
            # Skip empty files
            if os.path.getsize(tsv_file) == 0:
                print(f"⚠️ Skipping empty file: {tsv_file}")
                continue

            # Create output CSV filename
            csv_file = os.path.splitext(tsv_file)[0] + ".csv"

            print(f"📘 Converting: {tsv_file} → {csv_file}")

            # Read and save
            df = pd.read_csv(tsv_file, sep='\t')
            df.to_csv(csv_file, index=False)

            print(f"✅ Done: {csv_file}\n")

        except Exception as e:
            print(f"❌ Error converting {tsv_file}: {e}\n")

    print("🎉 All conversions completed!")
