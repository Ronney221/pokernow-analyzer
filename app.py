#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser(
        description="Process a raw CSV file through cleandata.py and then run script.py."
    )
    parser.add_argument("csv_file", help="Path to the raw CSV file")
    parser.add_argument("--player", required=True, help="Your player name (trimmed, e.g. 'rondog')")
    args = parser.parse_args()

    # Convert the input CSV file path to an absolute path.
    raw_csv = os.path.abspath(args.csv_file)
    if not os.path.exists(raw_csv):
        print(f"Error: The file {raw_csv} does not exist.")
        sys.exit(1)

    # Create a folder named after the input CSV (without extension) in the same directory.
    input_dir = os.path.dirname(raw_csv)
    base_name = os.path.splitext(os.path.basename(raw_csv))[0]
    output_folder = os.path.join(input_dir, base_name)
    os.makedirs(output_folder, exist_ok=True)

    # Define the cleaned file output path inside the created folder.
    cleaned_output = os.path.join(output_folder, "cleaned_data.csv")
    cleaned_output = os.path.abspath(cleaned_output)

    # Step 1: Run cleandata.py on the input CSV file.
    print(f"Running cleandata.py on {raw_csv}...")
    ret = subprocess.run(["python", "cleandata.py", raw_csv, "--output", cleaned_output])
    if ret.returncode != 0:
        print("Error running cleandata.py")
        sys.exit(ret.returncode)
    else:
        print(f"Cleaned data saved to {cleaned_output}")

    # Step 2: Set environment variable so that script.py uses the cleaned CSV.
    os.environ["CLEANED_INPUT"] = cleaned_output

    # Step 3: Run script.py with the required arguments.
    # script.py expects: csv_file and --player PLAYER
    print("Running script.py...")
    ret2 = subprocess.run(["python", "script.py", cleaned_output, "--player", args.player],
                            env=os.environ.copy())
    if ret2.returncode != 0:
        print("Error running script.py")
        sys.exit(ret2.returncode)
    else:
        print("script.py completed successfully.")

if __name__ == "__main__":
    main()
