import csv
import os

def debug_csv(file_path):
    print(f"Debugging: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            commas = line.count(',')
            print(f"  Line {i+1} has {commas} commas (expected {lines[0].count(',')})")

if __name__ == "__main__":
    import sys
    debug_csv("networks/ton/api.csv")
    debug_csv("networks/bsc/api.csv")
