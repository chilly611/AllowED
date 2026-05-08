#!/usr/bin/env python3
"""
Update enrollment statuses to realistic values for demo purposes.
- Students with HITL flags → hitl_review
- Clean students → ready_for_batch (80%), submitted (10%), certified (10%)
"""
import os, sys, random
from dotenv import dotenv_values
from supabase import create_client

config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
client = create_client(config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"])

# Get all HITL enrollment IDs
print("Fetching HITL flags...")
hitl = client.table("hitl_queue").select("enrollment_id").execute()
hitl_enrollment_ids = set(h["enrollment_id"] for h in hitl.data if h["enrollment_id"])
print(f"  {len(hitl_enrollment_ids)} enrollments have HITL flags")

# Mark HITL enrollments as hitl_review
if hitl_enrollment_ids:
    for eid in hitl_enrollment_ids:
        client.table("enrollments").update({"status": "hitl_review"}).eq("id", eid).execute()
    print(f"  ✓ Set {len(hitl_enrollment_ids)} enrollments to hitl_review")

# Get all remaining pending enrollments
print("\nFetching pending enrollments...")
pending = client.table("enrollments").select("id, institution_id").eq("status", "pending").execute()
print(f"  {len(pending.data)} pending enrollments")

# Distribute: 65% ready_for_batch, 20% submitted, 15% certified
random.seed(42)  # Reproducible
ready = submitted = certified = 0
for e in pending.data:
    roll = random.random()
    if roll < 0.65:
        status = "ready_for_batch"
        ready += 1
    elif roll < 0.85:
        status = "submitted"
        submitted += 1
    else:
        status = "certified"
        certified += 1
    client.table("enrollments").update({"status": status}).eq("id", e["id"]).execute()

print(f"  ✓ ready_for_batch: {ready}")
print(f"  ✓ submitted: {submitted}")
print(f"  ✓ certified: {certified}")
print(f"\nDone. Dashboard should now show realistic numbers.")
