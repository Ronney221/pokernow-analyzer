#!/usr/bin/env python
"""
CSV Data Organizer for Poker Hand History

This script reads a raw CSV file (with columns "entry", "at", "order") containing
poker hand history log messages. It parses each log entry to extract key details such as:
  - Hand start and end markers (e.g., "-- starting hand ..." and "-- ending hand ...")
  - Player actions like "shows", "collected", "folds", "calls", "bets", etc.
  - Player names when available

The parsed data is output to a cleaned CSV file that is easier to work with in further analyses.

Usage:
    python organize_csv.py path/to/raw_log.csv --output cleaned_log.csv
"""

import re
import pandas as pd
import argparse

def parse_entry(entry):
    """
    Parse a single log entry (a string) and extract details.

    Returns a dictionary with:
      - action_type: a label like "hand_start", "hand_end", "shows", "collected", "folds", etc.
      - hand_number: if applicable (for hand start/end markers)
      - player: extracted player name if available
      - amount: extracted amount if applicable (e.g., from "collected")
      - details: remaining details or the full cleaned text
    """
    # Remove surrounding quotes and normalize inner quotes
    cleaned = entry.strip().strip('"').replace('""', '"')
    
    # Check for hand start marker
    if cleaned.lower().startswith("-- starting hand"):
        m = re.search(r"-- starting hand #(\d+)", cleaned, re.IGNORECASE)
        hand_number = m.group(1) if m else None
        return {
            "action_type": "hand_start",
            "hand_number": hand_number,
            "player": None,
            "amount": None,
            "details": cleaned
        }
    
    # Check for hand end marker
    if cleaned.lower().startswith("-- ending hand"):
        m = re.search(r"-- ending hand #(\d+)", cleaned, re.IGNORECASE)
        hand_number = m.group(1) if m else None
        return {
            "action_type": "hand_end",
            "hand_number": hand_number,
            "player": None,
            "amount": None,
            "details": cleaned
        }
    
    # Check for a "shows" action
    if " shows " in cleaned.lower():
        m = re.search(r'^"?([^"]+)"?\s+shows\s+(.*)', cleaned, re.IGNORECASE)
        if m:
            player = m.group(1).strip()
            details = "shows " + m.group(2).strip()
            return {
                "action_type": "shows",
                "hand_number": None,
                "player": player,
                "amount": None,
                "details": details
            }
    
    # Check for "collected" action
    if " collected " in cleaned.lower():
        m = re.search(r'^"?([^"]+)"?\s+collected\s+([\d\.,]+)\s+from pot', cleaned, re.IGNORECASE)
        if m:
            player = m.group(1).strip()
            amount = m.group(2).strip()
            details = f"collected {amount} from pot"
            return {
                "action_type": "collected",
                "hand_number": None,
                "player": player,
                "amount": amount,
                "details": details
            }
    
    # Check for other standard actions (folds, calls, bets, checks, etc.)
    m = re.match(r'^"?([^"]+)"?\s+(.*)', cleaned)
    if m:
        player = m.group(1).strip()
        details = m.group(2).strip()
        # Determine action type from keywords
        action_type = "other"
        lowered = details.lower()
        if "folds" in lowered:
            action_type = "folds"
        elif "calls" in lowered:
            action_type = "calls"
        elif "bets" in lowered:
            action_type = "bets"
        elif "checks" in lowered:
            action_type = "checks"
        elif "stand up" in lowered:
            action_type = "stand_up"
        elif "quits" in lowered:
            action_type = "quits"
        return {
            "action_type": action_type,
            "hand_number": None,
            "player": player,
            "amount": None,
            "details": details
        }
    
    # Fallback: return the cleaned entry as unknown
    return {
        "action_type": "unknown",
        "hand_number": None,
        "player": None,
        "amount": None,
        "details": cleaned
    }

def main():
    parser = argparse.ArgumentParser(description="Organize and clean poker hand history CSV data.")
    parser.add_argument("csv_file", help="Path to the raw CSV file.")
    parser.add_argument("--output", default="cleaned_data.csv", help="Output CSV file for cleaned data.")
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.csv_file)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Check that the required column exists
    if "entry" not in df.columns:
        print("The CSV does not contain an 'entry' column. Please check the format.")
        return

    parsed_entries = []
    for index, row in df.iterrows():
        raw_entry = row["entry"]
        parsed = parse_entry(raw_entry)
        parsed["at"] = row.get("at")
        parsed["order"] = row.get("order")
        parsed_entries.append(parsed)

    cleaned_df = pd.DataFrame(parsed_entries)
    cleaned_df.to_csv(args.output, index=False)
    print(f"Cleaned CSV data saved to {args.output}")

if __name__ == "__main__":
    main()
