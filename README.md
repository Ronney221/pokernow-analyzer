# Poker Hand Analysis Tool

## Overview
This Python script analyzes poker hands to compute key player metrics based on preflop aggression. It processes a list of hands and extracts statistics for each player, including:

- **Hands Played**: The number of hands a player participated in.
- **VPIP (Voluntarily Put Money in Pot)**: The number and percentage of hands where a player contributed money preflop.
- **PFR (Preflop Raise)**: The number and percentage of hands where a player raised preflop.
- **Three-Bet (3bet)**: The number and percentage of hands where a player made a three-bet preflop.
- **Output CSV**: A generated CSV file summarizing player statistics.

This script is useful for poker players and analysts who want to track and improve their gameplay by studying preflop tendencies.

---
## Features
- Parses poker hand data to identify player participation.
- Computes key preflop metrics (VPIP, PFR, 3bet) for each player.
- Outputs results as a CSV file for easy visualization and analysis.
- Handles merging of three-bet data from separate sources.

---
## Installation
### Prerequisites
Ensure you have Python installed (preferably Python 3.7+). You will also need the following dependencies:

```sh
pip install pandas
```

---
## Usage
### Running the Script
1. Ensure you have a properly formatted JSON file containing hand history data (`hands_list`).
2. Run the script using:

```sh
python app.py 'pokernow_full_ledger.csv' --player pokernow_nickname
```

By default, the script will process the hands and output a CSV file containing player statistics.

### Expected Input
Your input data (`hands_list`) should be structured as a list of dictionaries, where each dictionary represents a single hand with player actions. Example structure:

```json
[
  {
    "hand_id": 1,
    "players": ["player1", "player2", "player3"],
    "preflop_aggression": [
      {"player": "player1", "action": "calls"},
      {"player": "player2", "action": "bets", "details": "3bet"}
    ]
  }
]
```

### Output
The script generates a CSV file (`player_metrics_chart.csv`) with columns:
- Player
- Hands Played
- VPIP
- VPIP %
- Preflop Raise
- Preflop Raise %
- Threebet
- Threebet %

---
## Customization
Modify the script to:
- Change sorting options for the CSV output.
- Include additional preflop metrics.
- Filter players based on activity levels.

---
## Contributing
Feel free to submit issues or pull requests to improve the script!

---
## License
This project is licensed under the MIT License.

