from typing import List, Tuple

PROGRAM_V1 = [
    ("Day 1 – Push (Chest/Shoulders/Triceps)", [
        ("Flat Barbell Bench Press", 3, 6, 8, "compound", 2.5),
        ("Incline Barbell Bench Press", 3, 8, 10, "compound", 2.5),
        ("Overhead Press (Barbell/DB)", 3, 6, 8, "compound", 2.5),
        ("Dumbbell/Cable Lateral Raise", 3, 12, 15, "accessory", 1.25),
        ("Rope Pushdown", 3, 12, 15, "accessory", 1.25),
    ]),
    ("Day 2 – Pull (Back/Biceps/Rear Delts/Traps)", [
        ("Weighted Pull-Ups", 3, 6, 10, "compound", 2.5),   # AMRAP acceptable within target
        ("Barbell Row", 3, 6, 8, "compound", 2.5),
        ("Lat Pulldown", 3, 10, 12, "compound", 2.5),
        ("Rear Delt Fly/Face Pull", 3, 12, 15, "accessory", 1.25),
        ("Barbell Curl", 3, 8, 10, "accessory", 1.25),
    ]),
    ("Day 3 – Rest / Core", [
        ("Cable Crunch", 3, 15, 15, "accessory", 1.25),
        ("Hanging Knee/Leg Raise", 3, 8, 20, "accessory", 1.25),
        ("Weighted Sit-Ups", 3, 15, 15, "accessory", 1.25),
    ]),
    ("Day 4 – Lower (Quads/Hams/Glutes/Calves)", [
        ("Back Squat", 3, 6, 8, "compound", 5.0),
        ("Romanian Deadlift", 3, 8, 10, "compound", 5.0),
        ("Bulgarian Split Squat", 3, 10, 12, "compound", 2.5),
        ("Standing Calf Raise", 3, 12, 15, "accessory", 2.5),
        ("Hip Thrust", 2, 8, 10, "compound", 5.0),
    ]),
    ("Day 5 – Push (Chest/Shoulders/Triceps)", [
        ("DB Flat Press", 3, 8, 10, "compound", 2.5),
        ("Incline DB Press/Cable Fly", 3, 10, 12, "compound", 2.5),
        ("Seated DB Overhead Press", 3, 8, 10, "compound", 2.5),
        ("Cable Lateral Raise", 3, 12, 15, "accessory", 1.25),
        ("Close-Grip Bench Press", 3, 6, 8, "compound", 2.5),
    ]),
    ("Day 6 – Pull (Back/Biceps/Rear Delts/Traps)", [
        ("Deadlift", 3, 4, 6, "compound", 5.0),
        ("Weighted Chin-Ups", 3, 6, 8, "compound", 2.5),
        ("One-Arm DB Row", 3, 8, 10, "compound", 2.5),
        ("Seated Cable Row", 3, 10, 12, "compound", 2.5),
        ("DB Rear Delt Fly", 3, 12, 15, "accessory", 1.25),
        ("Hammer Curl", 2, 10, 12, "accessory", 1.25),
    ]),
    ("Day 7 – Rest / Core (optional)", [
        # no planned work; may mirror Day 3 core if desired
    ]),
]

# Use PROGRAM_V1 for seeding
DAYS = PROGRAM_V1

# Map compound exercises to their RM keys (for Week 1–2 % seeding)
COMPOUND_RM_MAP = {
    "Back Squat": "squat",
    "Flat Barbell Bench Press": "bench",
    "Incline Barbell Bench Press": "bench",
    "Overhead Press (Barbell/DB)": "ohp",
    "DB Flat Press": "bench",
    "Seated DB Overhead Press": "ohp",
    "Barbell Row": "bench",                  # no direct RM; bench mapping yields reasonable % load guidance
    "Lat Pulldown": "bench",                 # guidance only (users adjust via logging)
    "Deadlift": "deadlift",
    "Romanian Deadlift": "deadlift",         # guidance only
    "Weighted Pull-Ups": "bench",            # guidance only
    "Weighted Chin-Ups": "bench",            # guidance only
    "One-Arm DB Row": "bench",               # guidance only
    "Seated Cable Row": "bench",             # guidance only
    "Close-Grip Bench Press": "bench",
    "Hip Thrust": "deadlift",                # guidance only
}

def round_to_2p5(x):
    if x is None: return None
    return round(round(float(x) / 2.5) * 2.5, 2)

def amrap_threshold(high):
    if high <= 8:   return 12
    if high == 10:  return 15
    if high == 12:  return 20
    if high == 15:  return 25
    if high >= 20:  return 30
    return 20

def compute_new_load(row: dict):
    load_last = row.get("load_last")
    if load_last in (None, ""):
        return None
    load_last = float(load_last)
    high = int(row["rep_high"]); inc = float(row["increment"] or 0.0)
    if row["category"] == "compound":
        sets = int(row["sets"])
        s1 = (row.get("s1") or 0); s2 = (row.get("s2") or 0); s3 = (row.get("s3") or 0)
        ok = (s1 >= high) and (s2 >= high) and (s3 >= high or sets < 3)
        return round_to_2p5(load_last + inc) if ok else round_to_2p5(load_last)
    else:
        thr = amrap_threshold(high)
        amr = (row.get("amrap") or 0)
        return round_to_2p5(load_last + inc) if amr >= thr else round_to_2p5(load_last)
