#!/usr/bin/env python3
"""
Fix training time for all Master's students affected by the wrong thresholds.
Correct: 6-8 units = 3/4 time, 4-5 = half time (was: 7-8 = 3/4, 5-6 = half)
"""
import os, sys
from dotenv import dotenv_values
from supabase import create_client

config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
client = create_client(config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"])

# Find all Master's students with enrollments
print("Fetching Master's student enrollments...")
students = client.table("students").select("id, first_name, last_name, academic_level").eq("academic_level", "masters").execute()
student_ids = {s["id"]: f"{s['first_name']} {s['last_name']}" for s in students.data}

if not student_ids:
    print("No master's students found.")
    sys.exit(0)

enrollments = client.table("enrollments").select("id, student_id, total_certifiable_units, training_time").in_("student_id", list(student_ids.keys())).execute()

fixed = 0
for e in enrollments.data:
    units = float(e["total_certifiable_units"] or 0)
    old_tt = e["training_time"]
    
    # Compute correct training time
    if units >= 9:
        correct_tt = "full_time"
    elif units >= 6:
        correct_tt = "three_quarter"
    elif units >= 4:
        correct_tt = "half_time"
    else:
        correct_tt = "less_than_half"
    
    # Compute correct rate of pursuit
    rop = round(units / 9.0, 4) if units > 0 else 0
    if rop > 1.0:
        rop = 1.0
    
    if old_tt != correct_tt:
        name = student_ids.get(e["student_id"], "Unknown")
        print(f"  Fixing {name}: {units} units — {old_tt} → {correct_tt}")
        client.table("enrollments").update({
            "training_time": correct_tt,
            "rate_of_pursuit": rop,
        }).eq("id", e["id"]).execute()
        fixed += 1

print(f"\nDone. Fixed {fixed} enrollment(s).")
