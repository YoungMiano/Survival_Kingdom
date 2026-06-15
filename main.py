"""
Kingdom Survival
A single-player terminal survival and wealth-building game.
Survive 100 days and build your fortune from humble beginnings.

Run with: python main.py
"""

import json
import os
import random
import sys
import time
from datetime import datetime


# ---------------------------------------------------------------------------
# Terminal colour support
# ---------------------------------------------------------------------------

def supports_color():
    """Return True if the terminal appears to support ANSI escape codes."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOR = supports_color()


class C:
    """ANSI colour code constants. All values fall back to empty strings when
    the terminal does not support colour, so the rest of the code never needs
    to branch on USE_COLOR directly."""
    RESET   = "\033[0m"        if USE_COLOR else ""
    BOLD    = "\033[1m"        if USE_COLOR else ""
    DIM     = "\033[2m"        if USE_COLOR else ""
    RED     = "\033[91m"       if USE_COLOR else ""
    GREEN   = "\033[92m"       if USE_COLOR else ""
    YELLOW  = "\033[93m"       if USE_COLOR else ""
    BLUE    = "\033[94m"       if USE_COLOR else ""
    MAGENTA = "\033[95m"       if USE_COLOR else ""
    CYAN    = "\033[96m"       if USE_COLOR else ""
    WHITE   = "\033[97m"       if USE_COLOR else ""
    GOLD    = "\033[33m"       if USE_COLOR else ""
    ORANGE  = "\033[38;5;208m" if USE_COLOR else ""


def col(text, color):
    """Wrap text in an ANSI colour code and reset afterwards."""
    return f"{color}{text}{C.RESET}"


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

WIDTH = 70  # characters wide for all drawn lines


def clear():
    """Clear the terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def hr(char="═", color=C.CYAN):
    """Print a full-width horizontal rule using the given character."""
    print(col(char * WIDTH, color))


def header(title, color=C.CYAN):
    """Print a centred title framed by two horizontal rules."""
    hr("═", color)
    pad = (WIDTH - len(title) - 2) // 2
    print(col("║" + " " * pad + title + " " * (WIDTH - pad - len(title) - 2) + "║", color))
    hr("═", color)


def subheader(title, color=C.BLUE):
    """Print a bold section title between two light horizontal rules."""
    hr("─", color)
    print(col(f"  {title}", C.BOLD + color))
    hr("─", color)


def box(lines, color=C.WHITE):
    """Print a list of strings inside a simple ruled box."""
    hr("─", color)
    for line in lines:
        print(f"  {line}")
    hr("─", color)


def pause(msg="Press Enter to continue..."):
    """Block until the player presses Enter."""
    input(col(f"\n  {msg}", C.DIM))


def confirm(prompt):
    """Ask a yes/no question and return True for yes, False for no."""
    while True:
        ans = input(col(f"  {prompt} (y/n): ", C.YELLOW)).strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print(col("  Please enter y or n.", C.RED))


def get_int(prompt, min_val=None, max_val=None):
    """Prompt for an integer, re-asking on bad input or out-of-range values."""
    while True:
        try:
            val = int(input(col(f"  {prompt}: ", C.YELLOW)).strip())
            if min_val is not None and val < min_val:
                print(col(f"  Must be at least {min_val}.", C.RED))
                continue
            if max_val is not None and val > max_val:
                print(col(f"  Must be at most {max_val}.", C.RED))
                continue
            return val
        except (ValueError, EOFError):
            print(col("  Please enter a valid number.", C.RED))


def get_choice(prompt, options):
    """Prompt for one of the given string options, re-asking on invalid input."""
    while True:
        try:
            val = input(col(f"  {prompt}: ", C.YELLOW)).strip()
            if val in options:
                return val
            print(col(f"  Invalid choice. Options: {', '.join(options)}", C.RED))
        except EOFError:
            return options[0]


def notify(msg, color=C.GREEN):
    """Print a single highlighted notification line."""
    print(col(f"\n  \u2746 {msg}", color))


def achievement_popup(name, desc):
    """Display an eye-catching achievement unlock banner."""
    print()
    hr("★", C.GOLD)
    print(col(f"  \U0001f3c6 ACHIEVEMENT UNLOCKED: {name}", C.GOLD + C.BOLD))
    print(col(f"     {desc}", C.YELLOW))
    hr("★", C.GOLD)


def stat_bar(label, value, maximum, width=20, color=C.GREEN):
    """Return a formatted string showing a stat as a coloured progress bar.

    The bar colour shifts to yellow below 60 % and red below 25 % so the
    player can spot danger at a glance.
    """
    filled = int((value / maximum) * width) if maximum > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = int((value / maximum) * 100) if maximum > 0 else 0
    bar_color = C.RED if pct < 25 else C.YELLOW if pct < 60 else color
    return f"{label:<12} {col(bar, bar_color)} {col(str(value), C.WHITE)}/{maximum}"


# ---------------------------------------------------------------------------
# Game constants
# ---------------------------------------------------------------------------

SAVE_FILE    = "savegame.json"
MAX_DAYS     = 100
MAX_HEALTH   = 100
MAX_ENERGY   = 100
FOOD_PER_DAY = 1   # units of food consumed each day during upkeep

# Items sold in the market. "effect" maps stat names to the amount applied.
MARKET_ITEMS = {
    "food":         {"base_price": 30,  "effect": {"food": 3}},
    "medicine":     {"base_price": 80,  "effect": {"health": 20}},
    "tool_kit":     {"base_price": 200, "effect": {"hunting_skill": 1}},
    "lucky_charm":  {"base_price": 150, "effect": {"luck": 1}},
    "energy_drink": {"base_price": 50,  "effect": {"energy": 30}},
}

# Properties the player can purchase. "bonus" is a tag string parsed in
# Player.passive_income(); None means income only.
PROPERTIES = {
    "small_house": {"cost": 2000,   "income": 20,  "desc": "Small House", "bonus": "health+5/day"},
    "farm":        {"cost": 5000,   "income": 80,  "desc": "Farm",        "bonus": "food+2/day"},
    "apartment":   {"cost": 10000,  "income": 150, "desc": "Apartment",   "bonus": None},
    "shop":        {"cost": 20000,  "income": 300, "desc": "Shop",        "bonus": "reputation+1/day"},
    "mansion":     {"cost": 100000, "income": 800, "desc": "Mansion",     "bonus": "luck+1/day"},
}

# Businesses the player can invest in.
BUSINESSES = {
    "food_stall":         {"cost": 1500,  "income": 40,  "desc": "Food Stall"},
    "market_shop":        {"cost": 4000,  "income": 100, "desc": "Market Shop"},
    "transport_business": {"cost": 8000,  "income": 180, "desc": "Transport Business"},
    "farm_business":      {"cost": 15000, "income": 300, "desc": "Farm Business"},
    "factory":            {"cost": 40000, "income": 700, "desc": "Factory"},
}

# Each achievement has a unique id, display name, description, and a lambda
# that takes a Player and returns True when the condition is met.
ACHIEVEMENTS = [
    {"id": "first_1k",       "name": "First Steps",      "desc": "Earn 1,000 money",            "check": lambda p: p.money >= 1000},
    {"id": "first_10k",      "name": "Getting There",    "desc": "Earn 10,000 money",           "check": lambda p: p.money >= 10000},
    {"id": "first_100k",     "name": "Wealthy Citizen",  "desc": "Earn 100,000 money",          "check": lambda p: p.money >= 100000},
    {"id": "first_500k",     "name": "Half a Million",   "desc": "Earn 500,000 money",          "check": lambda p: p.money >= 500000},
    {"id": "millionaire",    "name": "Millionaire",      "desc": "Earn 1,000,000 money",        "check": lambda p: p.money >= 1000000},
    {"id": "first_property", "name": "Homeowner",        "desc": "Purchase your first property","check": lambda p: len(p.properties) >= 1},
    {"id": "landlord",       "name": "Landlord",         "desc": "Own 3 properties",            "check": lambda p: len(p.properties) >= 3},
    {"id": "first_business", "name": "Entrepreneur",     "desc": "Start your first business",   "check": lambda p: len(p.businesses) >= 1},
    {"id": "mogul",          "name": "Business Mogul",   "desc": "Own 3 businesses",            "check": lambda p: len(p.businesses) >= 3},
    {"id": "survive_25",     "name": "Quarter Century",  "desc": "Survive 25 days",             "check": lambda p: p.day >= 25},
    {"id": "survive_50",     "name": "Halfway There",    "desc": "Survive 50 days",             "check": lambda p: p.day >= 50},
    {"id": "survive_75",     "name": "Veteran",          "desc": "Survive 75 days",             "check": lambda p: p.day >= 75},
    {"id": "survive_100",    "name": "Kingdom Survivor", "desc": "Survive all 100 days",        "check": lambda p: p.day >= 100},
    {"id": "master_hunter",  "name": "Master Hunter",    "desc": "Reach Hunting Skill 10",      "check": lambda p: p.hunting_skill >= 10},
    {"id": "master_trader",  "name": "Master Trader",    "desc": "Reach Trading Skill 10",      "check": lambda p: p.trading_skill >= 10},
    {"id": "lucky_star",     "name": "Lucky Star",       "desc": "Reach Luck 10",               "check": lambda p: p.luck >= 10},
    {"id": "well_known",     "name": "Well Known",       "desc": "Reach Reputation 10",         "check": lambda p: p.reputation >= 10},
    {"id": "full_belly",     "name": "Full Belly",       "desc": "Hold 20+ food at once",       "check": lambda p: p.food >= 20},
    {"id": "iron_will",      "name": "Iron Will",        "desc": "Survive with 5 or less health","check": lambda p: p.health <= 5 and p.alive},
    {"id": "hoarder",        "name": "Hoarder",          "desc": "Own 5+ inventory items",      "check": lambda p: sum(p.inventory.values()) >= 5},
    {"id": "explorer",       "name": "Explorer",         "desc": "Explore 20 times",            "check": lambda p: p.stats.get("explores", 0) >= 20},
    {"id": "hard_worker",    "name": "Hard Worker",      "desc": "Work 20 times",               "check": lambda p: p.stats.get("work_count", 0) >= 20},
    {"id": "investor",       "name": "Investor",         "desc": "Invest 10 times",             "check": lambda p: p.stats.get("invest_count", 0) >= 10},
    {"id": "hunter",         "name": "Seasoned Hunter",  "desc": "Hunt 15 times",               "check": lambda p: p.stats.get("hunt_count", 0) >= 15},
    {"id": "relic_finder",   "name": "Relic Hunter",     "desc": "Find an Ancient Relic",       "check": lambda p: p.inventory.get("ancient_relic", 0) >= 1},
]


# ---------------------------------------------------------------------------
# Exploration event table
# ---------------------------------------------------------------------------
# Each entry is a dict with:
#   "w"   - relative weight (higher = more common)
#   "msg" - the narrative line shown to the player
#   stat keys (money, food, health, energy, luck, reputation,
#              hunting_skill, trading_skill) - (min, max) tuples, may be negative
#   "inv_item" - optional item key added to the player's inventory
#   "special"  - optional tag for events that need custom handling
#
# Luck boosts the weight of events with w <= 5 at selection time,
# making rare finds slightly more likely for lucky players.

EXPLORE_EVENTS = [
    # Common positive finds (w=30)
    {"w": 30, "msg": "You find some coins on the road.",                       "money": (10, 50)},
    {"w": 30, "msg": "You gather wild berries.",                               "food": (1, 2)},
    {"w": 30, "msg": "You find an abandoned campfire with leftover food.",     "food": (1, 3)},
    {"w": 30, "msg": "You discover a coin purse someone dropped.",             "money": (20, 80)},
    {"w": 30, "msg": "You forage edible roots and mushrooms.",                 "food": (1, 3)},
    {"w": 30, "msg": "You find a small cache of supplies.",                    "food": (1, 2), "money": (10, 30)},

    # Uncommon positive finds (w=25)
    {"w": 25, "msg": "You stumble upon a lost traveller's satchel with coin.", "money": (30, 100)},
    {"w": 25, "msg": "You find freshwater and feel refreshed.",                "health": (5, 10)},
    {"w": 25, "msg": "You spot healing herbs and tend your wounds.",           "health": (5, 15)},
    {"w": 25, "msg": "You discover a shortcut, saving energy.",                "energy": (10, 20)},

    # Uncommon positive finds (w=15)
    {"w": 15, "msg": "You find a hidden stash of gold coins!",                 "money": (100, 300)},
    {"w": 15, "msg": "You discover an abandoned merchant's wagon with goods.", "food": (3, 6), "money": (50, 150)},
    {"w": 15, "msg": "You meet a friendly hermit who shares his meal.",        "food": (2, 4), "health": (5, 10)},
    {"w": 15, "msg": "You find an old medicine chest.",                        "health": (10, 25), "inv_item": "medicine"},
    {"w": 15, "msg": "You discover a lucky charm in the dirt.",                "luck": (1, 1), "inv_item": "lucky_charm"},
    {"w": 15, "msg": "You find an old tool kit.",                              "inv_item": "tool_kit"},
    {"w": 15, "msg": "You meet a travelling merchant selling cheap wares.",    "money": (0, 0), "special": "cheap_merchant"},
    {"w": 15, "msg": "You discover a secret garden with rare herbs.",          "health": (15, 30)},
    {"w": 15, "msg": "You find an old chest buried under leaves.",             "money": (80, 250)},
    {"w": 15, "msg": "You encounter a wise elder who teaches you a trick.",    "hunting_skill": (0, 1), "trading_skill": (0, 1)},

    # Uncommon negative encounters (w=12)
    {"w": 12, "msg": "A thief snatches your coin pouch!",                     "money": (-150, -50)},
    {"w": 12, "msg": "You twist your ankle on uneven ground.",                 "health": (-10, -5)},
    {"w": 12, "msg": "You wander too far and exhaust yourself.",               "energy": (-20, -10)},
    {"w": 12, "msg": "Bandits ambush you and steal your food.",                "food": (-3, -1)},
    {"w": 12, "msg": "You eat something suspicious and feel ill.",             "health": (-15, -5)},

    # Rare positive finds (w=5) - weight boosted by Luck stat
    {"w": 5, "msg": "You discover an abandoned cabin stocked with supplies!", "food": (5, 10), "money": (100, 300), "health": (10, 20)},
    {"w": 5, "msg": "You find a treasure map!",                               "inv_item": "treasure_map"},
    {"w": 5, "msg": "You unearth an ancient relic of great value!",           "inv_item": "ancient_relic", "money": (200, 500)},
    {"w": 5, "msg": "You discover a hidden vault with riches!",               "money": (400, 800)},
    {"w": 5, "msg": "A merchant gifts you a golden statue for helping him!",  "inv_item": "golden_statue", "money": (300, 600)},
    {"w": 5, "msg": "You find a rare gemstone glittering in a stream!",       "money": (300, 700)},
    {"w": 5, "msg": "You rescue a noble's child; he rewards you handsomely.", "money": (500, 1000), "reputation": (1, 2)},
    {"w": 5, "msg": "You discover ancient ruins with inscribed wisdom.",       "hunting_skill": (1, 1), "trading_skill": (1, 1), "luck": (1, 1)},

    # Very rare jackpots (w=2) - weight boosted by Luck stat
    {"w": 2, "msg": "You find a legendary buried treasure!",                  "money": (1000, 3000)},
    {"w": 2, "msg": "A wandering sage teaches you advanced trading secrets.",  "trading_skill": (2, 3)},
    {"w": 2, "msg": "A master hunter shares ancient hunting techniques.",      "hunting_skill": (2, 3)},
    {"w": 2, "msg": "You discover a dragon's hoard — just a small piece.",    "money": (2000, 5000)},
    {"w": 2, "msg": "Fortune smiles on you: a miracle windfall!",             "money": (1500, 4000), "luck": (1, 2)},

    # Mid-tier luck-influenced events (w=8)
    {"w": 8, "msg": "Your sharp eye spots a merchant's dropped purse.",        "money": (60, 200)},
    {"w": 8, "msg": "You find a well-travelled trade route and collect tolls.","money": (80, 250)},
    {"w": 8, "msg": "You discover a hidden spring with healing waters.",        "health": (20, 35), "energy": (15, 25)},
    {"w": 8, "msg": "You stumble into a bandit camp while they sleep and take their loot.", "money": (150, 400)},
    {"w": 8, "msg": "You find an exotic spice trader who overpays for your help.", "money": (120, 350)},
]


# ---------------------------------------------------------------------------
# End-of-day random event table
# ---------------------------------------------------------------------------
# Same structure as EXPLORE_EVENTS. Two additional boolean flags are used:
#   "property_bonus" - grants extra money if the player owns any property
#   "business_bonus" - grants extra money if the player owns any business

DAILY_EVENTS = [
    # Good events
    {"w": 15, "msg": "Good Harvest! Crops are plentiful.",                     "food": (2, 5)},
    {"w": 12, "msg": "A travelling merchant passes through. Busy day!",        "money": (30, 100)},
    {"w": 10, "msg": "Festival in town! Everyone is merry.",                   "health": (5, 10), "energy": (10, 20)},
    {"w": 10, "msg": "Lucky day — you find extra coin under your floorboard.", "money": (20, 80)},
    {"w": 8,  "msg": "A merchant fair opens. Business is booming.",            "money": (50, 200)},
    {"w": 8,  "msg": "You receive a gift from a grateful neighbour.",          "food": (1, 3), "money": (20, 60)},
    {"w": 8,  "msg": "Sunny weather lifts your spirits.",                      "energy": (10, 20), "health": (5, 10)},
    {"w": 6,  "msg": "You win a small lottery!",                               "money": (100, 400)},
    {"w": 5,  "msg": "A skilled healer visits town. You get treated.",         "health": (15, 30)},
    {"w": 5,  "msg": "Bumper crop season benefits everyone.",                  "food": (3, 7)},
    {"w": 4,  "msg": "Your reputation precedes you: a noble pays handsomely.", "money": (200, 500)},
    {"w": 4,  "msg": "A rare comet passes — locals say it brings luck.",       "luck": (1, 1)},
    {"w": 4,  "msg": "A distant relative sends you money.",                    "money": (100, 300)},
    {"w": 3,  "msg": "Treasure hunters pass through, sparking excitement.",    "money": (80, 250)},
    {"w": 3,  "msg": "You recall an old friend's trading secret.",             "trading_skill": (1, 1)},
    {"w": 3,  "msg": "A hunting elder passes on ancient knowledge.",           "hunting_skill": (1, 1)},
    {"w": 2,  "msg": "Grand lottery jackpot! You hold a winning ticket!",     "money": (500, 1500)},
    {"w": 2,  "msg": "A wandering bard sings your praises across the land.",  "reputation": (1, 2)},
    {"w": 2,  "msg": "An anonymous donor leaves a chest at your door.",        "money": (300, 800)},

    # Neutral events
    {"w": 12, "msg": "Tax collector visits. You pay your dues.",               "money": (-80, -20)},
    {"w": 10, "msg": "A minor dispute drains your time but not your coin.",    "energy": (-10, -5)},
    {"w": 8,  "msg": "Market prices fluctuate. Nothing major happens.",        "money": (-20, 20)},
    {"w": 8,  "msg": "Quiet day. Nothing extraordinary.",                      "energy": (-5, 5)},
    {"w": 6,  "msg": "A traveller stops for directions. No gain, no loss.",    "reputation": (0, 1)},

    # Bad events
    {"w": 15, "msg": "Drought reduces food supply.",                           "food": (-3, -1)},
    {"w": 12, "msg": "Bandits raid the outskirts. You lose some money.",       "money": (-100, -30)},
    {"w": 10, "msg": "Flood damages local farms.",                             "food": (-2, -1), "health": (-5, 0)},
    {"w": 8,  "msg": "A disease sweeps through town. You fall ill.",           "health": (-15, -5)},
    {"w": 8,  "msg": "Thieves break in and steal your supplies.",              "food": (-2, -1), "money": (-60, -20)},
    
