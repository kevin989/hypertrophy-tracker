from typing import List, Tuple

DAYS: List[Tuple[str, List[Tuple[str,int,int,int,str,float]]]] = [
    ("Day 1 – Push (Chest/Shoulders/Triceps)", [
        ("Flat Barbell Bench Press", 3, 6, 8, "compound", 2.5),
        ("Incline Barbell Press", 3, 8, 10, "accessory", 2.5),
        ("Overhead Press (Seated/Standing)", 3, 6, 8, "compound", 2.5),
        ("Lateral Raise (DB/Cable)", 3, 12, 15, "accessory", 1.25),
        ("Rope Pushdown", 3, 12, 15, "accessory", 1.25),
    ]),
    ("Day 2 – Pull (Back/Biceps/Rear Delts)", [
        ("Pull-Ups (weighted if needed)", 3, 6, 10, "compound", 2.5),
        ("Barbell Row", 3, 6, 8, "compound", 2.5),
        ("Lat Pulldown", 3, 10, 12, "accessory", 2.5),
        ("Rear Delt Fly / Face Pull", 3, 12, 15, "accessory", 1.25),
        ("Barbell Curl", 3, 8, 10, "accessory", 1.25),
    ]),
    ("Day 3 – Rest (Core)", [
        ("Cable Crunch", 3, 15, 15, "accessory", 1.25),
        ("Hanging Knees/Leg Raises", 3, 8, 20, "accessory", 1.25),
        ("Weighted Sit-Ups", 3, 15, 15, "accessory", 1.25),
    ]),
    ("Day 4 – Lower (Quads/Hams/Glutes/Calves)", [
        ("Back Squat", 3, 6, 8, "compound", 5),
        ("Romanian Deadlift", 3, 8, 10, "accessory", 2.5),
        ("Bulgarian Split Squat (per leg)", 3, 10, 12, "accessory", 2.5),
        ("Standing Calf Raise", 3, 12, 15, "accessory", 1.25),
        ("Hip Thrust (BB/DB)", 2, 8, 10, "accessory", 2.5),
    ]),
    ("Day 5 – Push", [
        ("DB Flat Press", 3, 8, 10, "accessory", 2.5),
        ("Incline DB Press / Cable Fly", 3, 10, 12, "accessory", 2.5),
        ("Seated DB Overhead Press", 3, 8, 10, "accessory", 2.5),
        ("Cable Lateral Raise", 3, 12, 15, "accessory", 1.25),
        ("Close-Grip Bench Press", 3, 6, 8, "compound", 2.5),
    ]),
    ("Day 6 – Pull", [
        ("Deadlift", 2, 4, 6, "compound", 5),
        ("Weighted Chin-Ups", 3, 6, 8, "compound", 2.5),
        ("One-Arm DB Row", 3, 8, 10, "accessory", 2.5),
        ("Seated Cable Row", 3, 10, 12, "accessory", 2.5),
        ("Rear Delt Fly", 3, 12, 15, "accessory", 1.25),
        ("Hammer Curl", 3, 10, 12, "accessory", 1.25),
    ]),
    ("Day 7 – Rest", []),
]

COMPOUND_RM_MAP = {
    "Back Squat": "squat",
    "Flat Barbell Bench Press": "bench",
    "Deadlift": "deadlift",
    "Overhead Press (Seated/Standing)": "ohp",
    "Close-Grip Bench Press": "bench",
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
