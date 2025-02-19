import pandas as pd
import re
import json
import os
import argparse
import sys

# --- Helper Functions ---

def extract_cards(details):
    """Extract card information from a details string."""
    match = re.search(r'\[([^\]]+)\]', details)
    if match:
        cards_str = match.group(1)
        cards = [card.strip(' "\n') for card in cards_str.split(',')]
        return cards
    return []

def extract_hole_cards(details):
    """Extract hole card information from details (e.g., 'Your hand is 5♣, 6♠')."""
    match = re.search(r'Your hand is\s*(.*)', details, re.IGNORECASE)
    if match:
        cards_str = match.group(1)
        cards = [card.strip(' "\n') for card in cards_str.split(',')]
        return cards
    return []

def row_to_dict(row):
    """Convert a pandas row to a plain dictionary."""
    return {
        'action_type': row['action_type'],
        'hand_number': row['hand_number'],
        'player': row['player'],
        'amount': row['amount'],
        'details': row['details'],
        'at': row['at'],
        'order': row['order']
    }

def extract_board_cards(player_text, details):
    """
    Given a player_text (e.g. "Turn: 3♦, J♦, 2♠") and details (e.g. "[K♣]"),
    this function:
      1. Removes the board prefix (Flop:, Turn:, or River:),
      2. Combines the remaining text from player_text and details,
      3. Inserts a comma before the details if one is missing,
      4. Ensures the result is enclosed in square brackets,
      5. Uses extract_cards() to extract the cards,
      6. And then strips any leading '[' from each card.
    """
    # Combine the strings.
    combined = (player_text + " " + details).strip()
    
    # Remove the board prefix if present.
    for prefix in ["flop:", "turn:", "river:"]:
        if combined.lower().startswith(prefix):
            combined = combined[len(prefix):].strip()
            break

    # Find the first '['; if it's not preceded by a comma, insert one.
    idx = combined.find('[')
    if idx != -1:
        if idx > 0 and combined[idx-1] != ',':
            combined = combined[:idx].rstrip() + ", " + combined[idx:]
    
    # Remove extra quotes.
    combined = combined.strip(' "')
    
    # Ensure the combined string starts with '[' and ends with ']'
    if not combined.startswith('['):
        combined = "[" + combined
    if not combined.endswith(']'):
        combined = combined + "]"
    
    # Extract cards using your existing function.
    cards = extract_cards(combined)
    # Remove any leading '[' from each card.
    cards = [card.lstrip('[').strip() for card in cards]
    return cards

def calculate_net_for_player(hands_list, player):
    """
    Calculate the net result for each hand for the specified player.
    Net = Collected amount (if any) - Invested amount (via preflop aggression)
    Returns a list of dictionaries with keys:
      "Hand Number", "Collected", "Invested", "Net"
    """
    results = []
    for hand in hands_list:
        hand_num = hand.get("hand_number")
        collected_sum = 0.0
        invested_sum = 0.0

        # Sum collected amounts for this player in this hand.
        for coll in hand.get("collected", []):
            coll_player = coll.get("player", "")
            if coll_player and coll_player.split('@')[0].strip().lower() == player.lower():
                try:
                    collected_sum += float(coll.get("amount", 0))
                except Exception:
                    pass

        # Sum invested amounts from preflop aggression events.
        for agg in hand.get("preflop_aggression", []):
            agg_player = agg.get("player", "")
            if agg_player and agg_player.split('@')[0].strip().lower() == player.lower():
                try:
                    invested_sum += float(agg.get("amount", 0))
                except Exception:
                    pass

        net_result = collected_sum - invested_sum

        # Record the hand if there's any activity.
        if invested_sum != 0 or collected_sum != 0:
            results.append({
                "Hand Number": hand_num,
                "Collected": collected_sum,
                "Invested": invested_sum,
                "Net": net_result
            })
    return results

def get_opponents_info(hand, my_player):
    """
    Returns a comma‐separated string of opponents (trimmed before '@')
    who reached showdown. For each opponent (from the hand's "shows" events)
    whose trimmed name is not my_player, it attempts to use the "details"
    field (which should contain their shown cards). If that’s not available,
    it checks hand["hole_cards"].
    """
    opponents = []
    for show in hand.get("shows", []):
        p = show.get("player")
        if isinstance(p, str):
            trimmed = p.split('@')[0].strip()
            if trimmed.lower() != my_player:
                # First, try to get shown cards from the "details" field.
                opp_cards = show.get("details", "").strip()
                # If no cards found, try hand["hole_cards"] for that opponent.
                if not opp_cards and "hole_cards" in hand:
                    for key, cards in hand["hole_cards"].items():
                        if isinstance(key, str) and key.split('@')[0].strip().lower() == trimmed.lower():
                            opp_cards = str(cards)
                            break
                if opp_cards:
                    opponents.append(f"{trimmed}: {opp_cards}")
                else:
                    opponents.append(trimmed)
    return ", ".join(opponents)


# --- Helper function: Get trimmed player names from a hand's actions ---
def get_players_in_hand(hand):
    players = set()
    for action in hand.get("actions", []):
        p = action.get("player")
        if isinstance(p, str) and "@" in p:
            players.add(p.split('@')[0].strip().lower())
    return players


# --- Create Folder Structure ---

input_filename = os.getenv("CLEANED_INPUT", "")
if not input_filename:
    raise ValueError("CLEANED_INPUT environment variable not set!")

df = pd.read_csv(input_filename)  # process the cleaned CSV as before

# Use the directory of the cleaned file as the base folder.
base_folder = os.path.basename(os.path.dirname(input_filename))
charts_folder = os.path.join(os.path.dirname(input_filename), "charts")
players_folder = os.path.join(os.path.dirname(input_filename), "players")

os.makedirs(charts_folder, exist_ok=True)
os.makedirs(players_folder, exist_ok=True)

# --- Parser Code ---
df = pd.read_csv(input_filename)  # expected columns: action_type, hand_number, player, amount, details, at, order
df.sort_values(by='order', inplace=True)

hands_list = []  # List to hold each hand's dictionary
current_hand = None

for idx, row in df.iterrows():
    act_type = str(row['action_type']).strip().lower()
    
    if act_type.startswith("hand_start"):
        if current_hand is not None:
            current_hand['pot_history'].append((current_hand['current_stage'], current_hand['pot_total']))
            hands_list.append(current_hand)
        hand_info = row_to_dict(row)
        hand_num = row['hand_number'] if pd.notnull(row['hand_number']) else None
        current_hand = {
            'hand_number': hand_num,
            'hand_start_info': hand_info,
            'dealer': None,
            'actions': [hand_info],
            'pot_total': 0.0,
            'pot_history': [],   # list of (stage, pot_total)
            'current_stage': 'preflop',
            'board': {},         # keys: 'flop', 'turn', 'river'
            'blinds': {},        # keys: 'small', 'big'
            'uncalled_bets': [],
            'collected': [],
            'shows': [],         # will store shows events (with hand number, stage, and board info)
            'hole_cards': {},
            'preflop_aggression': [],  # list of aggression actions with extra stage/board info
            'join_events': [],
            'quit_events': []
        }
    elif act_type.startswith("hand_end"):
        if current_hand is not None:
            action = row_to_dict(row)
            if pd.isnull(action['hand_number']) and current_hand['hand_number'] is not None:
                action['hand_number'] = current_hand['hand_number']
            current_hand['actions'].append(action)
            current_hand['pot_history'].append((current_hand['current_stage'], current_hand['pot_total']))
            hands_list.append(current_hand)
        current_hand = None
    else:
        # Skip processing if current_hand is None.
        if current_hand is None:
            continue
        
        action = row_to_dict(row)
        if pd.isnull(action['hand_number']) and current_hand['hand_number'] is not None:
            action['hand_number'] = current_hand['hand_number']
        
        act_lower = act_type
        details = str(action['details']) if pd.notnull(action['details']) else ""
        player = action['player'] if pd.notnull(action['player']) else ""
        try:
            amt = float(action['amount']) if pd.notnull(action['amount']) and action['amount'] != "" else 0.0
        except Exception:
            amt = 0.0

        if act_lower in ["bets", "calls"]:
            if amt == 0.0:
                m = re.search(r'(\d+(?:\.\d+)?)', details)
                if m:
                    amt = float(m.group(1))
            current_hand['pot_total'] += amt
            action['amount'] = amt
            current_hand['actions'].append(action)
            current_stage = current_hand['current_stage']
            board_info = current_hand['board'].copy()
            current_hand['preflop_aggression'].append({
                'player': player,
                'action': act_lower,
                'amount': amt,
                'details': details,
                'stage': current_stage,
                'board': board_info
            })
        elif act_lower == "folds":
            current_hand['actions'].append(action)
        elif act_lower == "shows":
            # Remove the prefix "shows a" (case-insensitive) from details, if present.
            cleaned_details = details
            prefix = "shows a"
            if details.lower().startswith(prefix):
                cleaned_details = details[len(prefix):].strip()
            # Create the show entry using the cleaned details.
            show_entry = {
                'hand_number': current_hand['hand_number'],
                'player': player,
                'details': cleaned_details,
                'pot_total': current_hand['pot_total'],
                'stage': current_hand['current_stage'],
                'board': current_hand['board'].copy(),
                'preflop_aggression': [x for x in current_hand['preflop_aggression'] if x['player'] == player]
            }
            current_hand['shows'].append(show_entry)
            current_hand['actions'].append(action)
        elif act_lower == "collected":
            current_hand['collected'].append({
                'player': player,
                'amount': amt,
                'details': details,
                'at': action['at']
            })
            current_hand['actions'].append(action)
        elif act_lower == "other":
            lower_player = str(action['player']).strip() if pd.notnull(action['player']) else ""
            lower_details = details.strip() if details else ""
            lower_player_l = lower_player.lower()
            lower_details_l = lower_details.lower()
            
            # NEW: Check if this "other" action contains a raise.
            if "raises to" in lower_details_l:
                m = re.search(r'raises to\s+(\d+(?:\.\d+)?)', lower_details_l)
                if m:
                    raise_amt = float(m.group(1))
                    current_hand['pot_total'] += raise_amt
                    current_stage = current_hand['current_stage']
                    board_info = current_hand['board'].copy()
                    # Append this aggression event.
                    current_hand['preflop_aggression'].append({
                        'player': player,
                        'action': "raises",
                        'amount': raise_amt,
                        'details': details,
                        'stage': current_stage,
                        'board': board_info,
                        'at': action.get('at')
                    })
            # Now process board events.
            if lower_player_l.startswith("flop:") or lower_details_l.startswith("flop:"):
                board_cards = extract_board_cards(action['player'], details)
                current_hand['board']['flop'] = board_cards
                current_hand['pot_history'].append(('preflop', current_hand['pot_total']))
                current_hand['current_stage'] = 'flop'
            elif lower_player_l.startswith("turn:") or lower_details_l.startswith("turn:"):
                board_cards = extract_board_cards(action['player'], details)
                current_hand['board']['turn'] = board_cards
                current_hand['pot_history'].append(('flop', current_hand['pot_total']))
                current_hand['current_stage'] = 'turn'
            elif lower_player_l.startswith("river:") or lower_details_l.startswith("river:"):
                board_cards = extract_board_cards(action['player'], details)
                current_hand['board']['river'] = board_cards
                current_hand['pot_history'].append(('turn', current_hand['pot_total']))
                current_hand['current_stage'] = 'river'
            
            # Process remaining "other" actions (blinds, uncalled bets, hole cards, join/quit events)
            if "small blind" in lower_details_l:
                current_hand['blinds']['small'] = {'player': player, 'amount': amt}
                current_hand['pot_total'] += amt
            elif "big blind" in lower_details_l:
                current_hand['blinds']['big'] = {'player': player, 'amount': amt}
                current_hand['pot_total'] += amt
            if "uncalled bet" in lower_details_l:
                current_hand['uncalled_bets'].append({'player': player, 'amount': amt, 'details': details})
            if "your hand is" in lower_details_l:
                hole_cards = extract_hole_cards(details)
                current_hand['hole_cards'][player] = hole_cards
            if "joined the game" in lower_details_l:
                current_hand['join_events'].append({'player': player, 'details': details, 'at': action['at']})
            if "quits" in lower_details_l:
                current_hand['quit_events'].append({'player': player, 'details': details, 'at': action['at']})
            
            current_hand['actions'].append(action)


if current_hand is not None:
    current_hand['pot_history'].append((current_hand['current_stage'], current_hand['pot_total']))
    hands_list.append(current_hand)

# --- Analysis Functions ---

def get_players_in_hand(hand):
    """Return a set of valid player names (strings containing '@') from the hand's actions."""
    players = set()
    for action in hand.get('actions', []):
        p = action.get('player')
        if isinstance(p, str) and "@" in p:
            players.add(p)
    return players

def compute_player_metrics(hands_list):
    """
    Compute player metrics:
      - hands_played: count of hands the player participated in
      - vpip: count of hands in which the player had any preflop aggression (calls or bets)
      - pfr: count of hands in which the player's preflop aggression was a bet (considered a raise)
      - threebet: count of hands in which the player's preflop aggression includes the keyword "3bet"
    
    For each hand, we use the preflop_aggression events recorded.
    """
    metrics = {}
    
    for hand in hands_list:
        players = get_players_in_hand(hand)
        for p in players:
            if p not in metrics:
                metrics[p] = {'hands_played': 0, 'vpip': 0, 'pfr': 0, 'threebet': 0}
            metrics[p]['hands_played'] += 1
        
        preflop_actions = hand.get('preflop_aggression', [])
        vpip_players = set()
        pfr_players = set()
        threebet_players = set()
        
        for act in preflop_actions:
            player = act.get('player')
            if not player:
                continue
            # Count any preflop aggression (calls or bets) toward VPIP.
            vpip_players.add(player)
            # Consider an action of "bets" as a preflop raise.
            if act.get('action') == "bets":
                pfr_players.add(player)
            # Check for "3bet" in details.
            if "3bet" in act.get('details', "").lower():
                threebet_players.add(player)
        
        for p in vpip_players:
            metrics.setdefault(p, {'hands_played': 0, 'vpip': 0, 'pfr': 0, 'threebet': 0})
            metrics[p]['vpip'] += 1
        for p in pfr_players:
            metrics.setdefault(p, {'hands_played': 0, 'vpip': 0, 'pfr': 0, 'threebet': 0})
            metrics[p]['pfr'] += 1
        for p in threebet_players:
            metrics.setdefault(p, {'hands_played': 0, 'vpip': 0, 'pfr': 0, 'threebet': 0})
            metrics[p]['threebet'] += 1
    
    for player, data in metrics.items():
        hp = data['hands_played']
        data['vpip_pct'] = round(data['vpip'] / hp * 100, 2) if hp else 0
        data['pfr_pct'] = round(data['pfr'] / hp * 100, 2) if hp else 0
        data['threebet_pct'] = round(data['threebet'] / hp * 100, 2) if hp else 0
    
    return metrics


def compute_average_pot_by_stage(hands_list):
    """Compute average pot size at each stage from the pot_history of each hand."""
    stage_totals = {'preflop': [], 'flop': [], 'turn': [], 'river': []}
    
    for hand in hands_list:
        for stage, pot in hand.get('pot_history', []):
            if stage in stage_totals:
                stage_totals[stage].append(pot)
    
    averages = {}
    for stage, pots in stage_totals.items():
        averages[stage] = round(sum(pots) / len(pots), 2) if pots else 0.0
    return averages

def link_shows_with_preflop_aggression(hands_list):
    """
    Build a list of show events (with hand number, stage, board, and linked aggression actions)
    and then sort them in descending order by the maximum aggression amount for actions
    with stage "preflop".
    """
    show_links = []
    for hand in hands_list:
        for show in hand.get('shows', []):
            show_links.append(show)
    
    def max_preflop_amount(show):
        preflop_actions = [
            aggression.get('amount', 0)
            for aggression in show.get('preflop_aggression', [])
            if aggression.get('stage') == 'preflop'
        ]
        return max(preflop_actions) if preflop_actions else 0
    
    show_links.sort(key=lambda x: max_preflop_amount(x), reverse=True)
    return show_links

# --- Analysis Output ---

# Link shows events with aggression.
shows_with_aggression = link_shows_with_preflop_aggression(hands_list)
#print("\nLinked Shows with Aggression (first 10, sorted by highest preflop aggression):")
first10_shows_with_aggression = shows_with_aggression[:10]
#print(json.dumps(first10_shows_with_aggression, indent=2))

# --- Build a DataFrame for Show Events with Preflop Aggression ---

rows = []
for show in shows_with_aggression:
    hand_number = show.get('hand_number')
    player_full = show.get('player', '')
    player = player_full.split('@')[0].strip() if "@" in player_full else player_full.strip()
    show_details = show.get('details')
    # Skip if show_details does not contain a comma (i.e. only one card shown)
    if show_details is None or "," not in show_details:
        continue
    
    # Filter linked aggression actions to only those with stage "preflop" and amount > 2.0.
    preflop_aggs = [
        agg for agg in show.get('preflop_aggression', [])
        if agg.get('stage') == 'preflop' and agg.get('amount', 0) > 2.0
    ]
    
    if preflop_aggs:
        for i, agg in enumerate(preflop_aggs):
            if i == 0:
                bet_level = "raise"
            else:
                bet_level = f"{i+2}bet"  # second becomes "3bet", third "4bet", etc.
            rows.append({
                'Hand Number': hand_number,
                'Player': player,
                'Show Details': show_details,
                'Preflop Amount': agg.get('amount'),
                'Bet Level': bet_level,
            })
    else:
        # If no aggression entries pass the filter, skip this show.
        continue

df_shows = pd.DataFrame(rows)

# Convert "Hand Number" to numeric to ensure proper sorting.
df_shows['Hand Number'] = pd.to_numeric(df_shows['Hand Number'], errors='coerce')

# Assuming df_shows is already built with columns including "Hand Number" and "Preflop Amount"
df_sorted = df_shows.sort_values(by=["Preflop Amount", "Hand Number"], ascending=[False, True]).reset_index(drop=True)

# Insert a blank row after every unique hand number.
separator = {col: "" for col in df_sorted.columns}
rows_with_sep = []
current_hand_num = None
for i, row in df_sorted.iterrows():
    hand_num = row["Hand Number"]
    if current_hand_num is None:
        current_hand_num = hand_num
    elif hand_num != current_hand_num:
        rows_with_sep.append(separator)
        current_hand_num = hand_num
    rows_with_sep.append(row.to_dict())
df_with_separators = pd.DataFrame(rows_with_sep)

# Export the full chart with separators to the charts subfolder.
full_chart_path = os.path.join(charts_folder, "full_shows_chart.csv")
df_with_separators.to_csv(full_chart_path, index=False)


# --- Create and Export Separate DataFrames for Each Unique Bet Level ---

def bet_level_key(level):
    """Custom key to sort bet levels: 'raise' comes first, then numeric bet levels."""
    level = level.lower()
    if level == "raise":
        return 1
    else:
        # Extract numeric part from something like "3bet" or "4bet"
        nums = re.findall(r'\d+', level)
        if nums:
            return int(nums[0])
        else:
            return float('inf')

# Get unique bet levels, then sort them using the custom key.
bet_levels = df_shows["Bet Level"].dropna().unique()
bet_levels = sorted(bet_levels, key=bet_level_key)

charts = {}
for level in bet_levels:
    chart_df = df_shows[df_shows["Bet Level"] == level].copy()
    # Sort by "Preflop Amount" descending, then by "Hand Number" ascending.
    chart_df.sort_values(by=["Preflop Amount", "Hand Number"], ascending=[False, True], inplace=True)
    charts[level] = chart_df
    csv_filename = f"chart_{level.replace(' ', '_')}.csv"
    csv_path = os.path.join(charts_folder, csv_filename)
    chart_df.to_csv(csv_path, index=False)
   # print(f"\nChart for Bet Level '{level}' exported to {csv_path}:")
   # print(chart_df.head(20))



# --- Build and Export Player Data (Only Raise/3bet/4bet with Show Details, Amount > 2.0) ---
players_data = {}  # mapping: player (trimmed) -> list of aggression rows for that hand

for hand in hands_list:
    hand_num = hand.get('hand_number')
    
    # Group preflop aggression events by player (only those with stage "preflop" and amount > 2.0)
    player_aggs = {}
    for agg in hand.get('preflop_aggression', []):
        if agg.get('stage') == 'preflop' and agg.get('amount', 0) > 2.0:
            p_full = agg.get('player', '')
            p_trim = p_full.split('@')[0].strip() if "@" in p_full else p_full.strip()
            if p_trim not in player_aggs:
                player_aggs[p_trim] = []
            player_aggs[p_trim].append(agg)
    
    # Get the show details for each player in this hand (if available) only if they show both cards.
    show_details_by_player = {}
    for show in hand.get('shows', []):
        p_full = show.get('player', '')
        p_trim = p_full.split('@')[0].strip() if "@" in p_full else p_full.strip()
        details = show.get('details')
        if details and "," in details:
            show_details_by_player[p_trim] = details
    
    # For each player in this hand, process their aggression events only if they have show details.
    for player, aggs in player_aggs.items():
        if player not in show_details_by_player:
            continue  # Skip if no valid show details.
        # Sort aggression events for this player by "amount" descending.
        aggs.sort(key=lambda x: x.get('amount', 0), reverse=True)
        for i, agg in enumerate(aggs):
            if i == 0:
                bet_level = "raise"
            else:
                bet_level = f"{i+2}bet"  # i=1 becomes "3bet", etc.
            row_data = {
                'Hand Number': hand_num,
                'Show Details': show_details_by_player.get(player),
                'Preflop Amount': agg.get('amount'),
                'Bet Level': bet_level
            }
            if player not in players_data:
                players_data[player] = []
            players_data[player].append(row_data)

# Export each player's aggregated aggression data to a separate CSV file in the players subfolder.
for player, rows_list in players_data.items():
    player_df = pd.DataFrame(rows_list)
    player_df.sort_values(by=["Preflop Amount", "Hand Number"], ascending=[False, True], inplace=True)
    safe_player = player.replace(" ", "_")
    player_csv = os.path.join(players_folder, f"{safe_player}.csv")
    player_df.to_csv(player_csv, index=False)
    print(f"\nExported aggression data for player '{player}' to {player_csv}")


# Compute average pot sizes at each stage.
avg_pot_by_stage = compute_average_pot_by_stage(hands_list)
print("\nAverage Pot Sizes by Stage:")
print(json.dumps(avg_pot_by_stage, indent=2))



# Use the computed player metrics from above
player_metrics = compute_player_metrics(hands_list)

# Build a list of dictionaries for our chart.
chart_data = []
for player, data in player_metrics.items():
    # Trim the player's name to everything before the '@'
    trimmed_player = player.split('@')[0].strip() if "@" in player else player.strip()
    chart_data.append({
        'Player': trimmed_player,
        'Hands Played': data['hands_played'],
        'VPIP': data['vpip'],
        'VPIP %': data['vpip_pct'],
        'Preflop Raise': data['pfr'],
        'Preflop Raise %': data['pfr_pct'],
        'Threebet': data['threebet'],
        'Threebet %': data['threebet_pct']
    })

# Create a DataFrame from the chart data.
df_metrics = pd.DataFrame(chart_data)

# Optionally, sort by Hands Played or VPIP % (for example, descending by VPIP %)
df_metrics.sort_values(by='VPIP %', ascending=False, inplace=True)

# Calculate threebet statistics using the chart data.
# Assume df_shows is the DataFrame built from show events with columns including "Bet Level", "Hand Number", and "Player".

# Filter to only rows with Bet Level == "3bet"
df_3bet = df_shows[df_shows["Bet Level"] == "3bet"].copy()

# Trim player names to before the "@".
df_3bet["Player"] = df_3bet["Player"].apply(lambda x: x.split('@')[0].strip() if "@" in x else x.strip())

# Group by player and count the number of unique hands that had a 3bet.
threebet_counts = df_3bet.groupby("Player")["Hand Number"].nunique().reset_index()
threebet_counts.rename(columns={"Hand Number": "threebet_count"}, inplace=True)

# Now, assuming you have a DataFrame df_metrics built from compute_player_metrics,
# which has a "Player" column (trimmed similarly) and "Hands Played":
df_metrics["Player"] = df_metrics["Player"].apply(lambda x: x.split('@')[0].strip() if "@" in x else x.strip())

# Merge the threebet counts with the player metrics.
df_metrics_updated = df_metrics.merge(threebet_counts, on="Player", how="left")
df_metrics_updated["threebet_count"] = df_metrics_updated["threebet_count"].fillna(0)

# Remove the original "Threebet" column and use the new one
if "Threebet" in df_metrics_updated.columns:
    df_metrics_updated.drop(columns=["Threebet"], inplace=True)
df_metrics_updated.rename(columns={"threebet_count": "Threebet"}, inplace=True)

# Calculate a threebet percentage (number of hands with a 3bet relative to total hands played).
df_metrics_updated["Threebet %"] = round(df_metrics_updated["Threebet"] / df_metrics_updated["Hands Played"] * 100, 2)

# Assuming df_metrics_updated is our merged DataFrame with the columns:
# "Player", "Hands Played", "VPIP", "VPIP %", "Preflop Raise", "Preflop Raise %", "Threebet", "Threebet %"
desired_order = ["Player", "Hands Played", "VPIP", "Preflop Raise", "Threebet", "VPIP %", "Preflop Raise %", "Threebet %"]

df_metrics_reordered = df_metrics_updated[desired_order]

# Define the output file path for the player metrics chart.
output_metrics_csv = os.path.join(charts_folder, "player_metrics_chart.csv")
df_metrics_reordered.to_csv(output_metrics_csv, index=False)
print("\nPlayer Metrics Chart saved to:", output_metrics_csv)


# --- Test: Print out board information for the first few hands with board data ---
# print("\nSample Board Data from Parsed Hands:")
# for hand in hands_list:
#     hand_num = hand.get('hand_number')
#     board = hand.get('board', {})
#     if board.get('flop') or board.get('turn') or board.get('river'):
#         print(f"Hand {hand_num}:")
#         if board.get('flop'):
#             print("  Flop:", board.get('flop'))
#         if board.get('turn'):
#             print("  Turn:", board.get('turn'))
#         if board.get('river'):
#             print("  River:", board.get('river'))




# THIS SECTION IS FOR TOP 10 HANDS AND WORST 10 HANDS





# --- Assume hands_list is already populated by your parser code ---

# For this example, we get the player name from the CLI.
parser = argparse.ArgumentParser(description="Analyze net profit/loss per hand for a given player.")
parser.add_argument("csv_file", help="Path to the cleaned CSV file (for context)")
parser.add_argument("--player", required=True, help="Your player name (the text to the left of '@')")
args = parser.parse_args()

# --- Net Analysis for the given player ---
my_player = args.player.strip().lower()
net_details = []
for hand in hands_list:
    hand_num = hand.get("hand_number")
    
    # Check if our player participated.
    participated = False
    if "hole_cards" in hand:
        for key in hand["hole_cards"]:
            if key.split('@')[0].strip().lower() == my_player:
                participated = True
                break
    if not participated:
        for agg in hand.get("preflop_aggression", []):
            if agg.get("player", "").split('@')[0].strip().lower() == my_player:
                participated = True
                break
    if not participated:
        continue

    # Sum invested from preflop aggression.
    invested = 0.0
    for agg in hand.get("preflop_aggression", []):
        if agg.get("player", "").split('@')[0].strip().lower() == my_player:
            try:
                invested += float(agg.get("amount", 0))
            except Exception:
                pass

    # Sum collected amounts for our player.
    collected = 0.0
    for coll in hand.get("collected", []):
        coll_player = coll.get("player", "")
        try:
            amt = float(coll.get("amount", 0))
        except Exception:
            amt = 0.0
        if coll_player and coll_player.split('@')[0].strip().lower() == my_player:
            collected += amt

    net = collected - invested

    # Get our hole cards.
    my_cards = None
    if "hole_cards" in hand and hand["hole_cards"]:
        for key, cards in hand["hole_cards"].items():
            if key.split('@')[0].strip().lower() == my_player:
                my_cards = cards
                break
    if my_cards is None:
        for show in hand.get("shows", []):
            if show.get("player", "").split('@')[0].strip().lower() == my_player:
                det = show.get("details", "")
                prefix = "shows a"
                if det.lower().startswith(prefix):
                    my_cards = det[len(prefix):].strip()
                else:
                    my_cards = det.strip()
                break
    if my_cards is None:
        my_cards = ""

    # Get board cards.
    board = hand.get("board", {})
    flop = board.get("flop", [])
    turn = board.get("turn", [])
    river = board.get("river", [])

    # Pot size: use the last pot_total from pot_history.
    pot_size = hand["pot_history"][-1][1] if hand.get("pot_history") else None

    # Determine Opponent info using the helper.
    opponent = get_opponents_info(hand, my_player)

    net_details.append({
        "Hand Number": hand_num,
        "My Cards": my_cards,
        "Flop": flop,
        "Turn": turn,
        "River": river,
        "Invested": invested,
        "Collected": collected,
        "Net": net,
        "Pot Size": pot_size,
        "Opponent": opponent
    })

df_net = pd.DataFrame(net_details)
if df_net.empty:
    print(f"No net results found for player '{my_player}'.")
    sys.exit(0)

# For winning hands, sort descending; for losing, ascending.
df_wins = df_net[df_net["Net"] > 0].sort_values(by="Net", ascending=False).head(10)
df_losses = df_net[df_net["Net"] < 0].sort_values(by="Net", ascending=True).head(10)

# Determine the output folder: create a "hands" folder in the same directory as the cleaned CSV.
input_filename = os.getenv("CLEANED_INPUT", "")
if not input_filename:
    raise ValueError("CLEANED_INPUT environment variable not set!")
input_dir = os.path.dirname(os.path.abspath(input_filename))
hands_folder = os.path.join(input_dir, "hands")
os.makedirs(hands_folder, exist_ok=True)

# Export results.
win_csv = os.path.join(hands_folder, f"{my_player}_top10_wins.csv")
loss_csv = os.path.join(hands_folder, f"{my_player}_top10_losses.csv")
df_wins.to_csv(win_csv, index=False)
df_losses.to_csv(loss_csv, index=False)

print("\nTop 10 Winning Hands:")
print(df_wins.to_string(index=False))
print(f"\nTop 10 winning hands saved to {win_csv}")

print("\nTop 10 Losing Hands:")
print(df_losses.to_string(index=False))
print(f"\nTop 10 losing hands saved to {loss_csv}")

#there is a bug for the losing hands, hand 122 i all inned and everyone folded, however it says i only collected the pot and didn't collect the all in i put in and nobody called 
#other,,Uncalled bet of 508.88 returned to,,"""rondo @ UjXI8JaXcs",2025-02-19T07:54:22.787Z,173995166278700

# # --- Assume hands_list is already generated by your parser code ---

# parser = argparse.ArgumentParser(
#     description="Generate overall net analysis across all players."
# )
# parser.add_argument("csv_file", help="Path to the cleaned CSV file (for context)")
# args = parser.parse_args()

# # (If hands_list is not already generated, ensure your parser code runs to populate it.)
# if 'hands_list' not in globals():
#     print("Error: hands_list not found. Ensure your parser code has generated hands_list.")
#     sys.exit(1)

# all_net_details = []
# for hand in hands_list:
#     hand_num = hand.get("hand_number")
#     # Get board cards and pot size.
#     board = hand.get("board", {})
#     flop = board.get("flop", [])
#     turn = board.get("turn", [])
#     river = board.get("river", [])
#     pot_size = hand["pot_history"][-1][1] if hand.get("pot_history") else None

#     # Get all participating players in this hand.
#     players = get_players_in_hand(hand)
#     for player in players:
#         # Compute invested: sum all preflop aggression for this player.
#         invested = 0.0
#         for agg in hand.get("preflop_aggression", []):
#             if agg.get("player", "").split('@')[0].strip().lower() == player:
#                 try:
#                     invested += float(agg.get("amount", 0))
#                 except Exception:
#                     pass
#         # Compute collected: sum all collected events for this player.
#         collected = 0.0
#         for coll in hand.get("collected", []):
#             if coll.get("player", "").split('@')[0].strip().lower() == player:
#                 try:
#                     collected += float(coll.get("amount", 0))
#                 except Exception:
#                     pass
#         net = collected - invested

#         # Retrieve player's hole cards.
#         my_cards = ""
#         if "hole_cards" in hand:
#             for key, cards in hand["hole_cards"].items():
#                 if key.split('@')[0].strip().lower() == player:
#                     my_cards = cards
#                     break

#         # (For opponents, you could extend this logic if desired.)
#         # For now, we'll leave opponent blank.
#         opponent = ""

#         all_net_details.append({
#             "Hand Number": hand_num,
#             "Player": player,  # This is the trimmed (lowercase) player name.
#             "My Cards": my_cards,
#             "Flop": flop,
#             "Turn": turn,
#             "River": river,
#             "Invested": invested,
#             "Collected": collected,
#             "Net": net,
#             "Pot Size": pot_size
#             # You can add "Opponent" here if needed.
#         })

# # Create a DataFrame from all net details.
# df_all = pd.DataFrame(all_net_details)

# if df_all.empty:
#     print("No net results found across hands.")
#     sys.exit(0)

# # For overall analysis, we might want to sort by Net across all hands.
# df_wins = df_all[df_all["Net"] > 0].sort_values(by="Net", ascending=False).head(10)
# df_losses = df_all[df_all["Net"] < 0].sort_values(by="Net", ascending=True).head(10)

# # Determine the output folder: create a "hands" folder in the same directory as the cleaned CSV.
# input_filename = os.getenv("CLEANED_INPUT", "")
# if not input_filename:
#     input_filename = os.path.abspath(args.csv_file)
# input_dir = os.path.dirname(os.path.abspath(input_filename))
# hands_folder = os.path.join(input_dir, "hands")
# os.makedirs(hands_folder, exist_ok=True)

# # Export overall top 10 winning and losing hands.
# wins_csv = os.path.join(hands_folder, "overall_top10_wins.csv")
# loss_csv = os.path.join(hands_folder, "overall_top10_losses.csv")
# df_wins.to_csv(wins_csv, index=False)
# df_losses.to_csv(loss_csv, index=False)

# print("\nOverall Top 10 Winning Hands:")
# print(df_wins.to_string(index=False))
# print(f"\nOverall top winning hands saved to {wins_csv}")

# print("\nOverall Top 10 Losing Hands:")
# print(df_losses.to_string(index=False))
# print(f"\nOverall top losing hands saved to {loss_csv}")