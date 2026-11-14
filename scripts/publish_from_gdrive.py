from datetime import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo
import requests

FOLDER_ID = "1i5pSM8yPiWII02c6af3tD5tJSRs44Z_C"
GDRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
BUFFER_API_URL = "https://api.buffer.com"
PUBLISHED_LEDGER = "published.json"
ET_TZ = ZoneInfo("America/New_York")

# Exact CALENDER.md schedule (ET)
CALENDAR_SLOTS_ET = {
    "D05": "2026-11-13T19:00:00",
    "D06": "2026-11-14T11:00:00",
    "D07": "2026-11-15T20:30:00",
    "D08": "2026-11-16T20:00:00",
    "D09": "2026-11-17T20:00:00",
    "D10": "2026-11-18T12:00:00",
    "D11": "2026-11-19T08:30:00",
    "D12": "2026-11-20T19:00:00",
    "D13": "2026-11-21T11:00:00",
    "D14": "2026-11-22T20:30:00",
    "D16": "2026-11-24T20:00:00",
    "D19": "2026-11-27T19:00:00",
    "D21": "2026-11-29T20:30:00",
    "D22": "2026-11-30T20:00:00",
    "D23": "2026-12-01T12:00:00",
    "D24": "2026-12-02T18:00:00",
    "D25": "2026-12-03T08:30:00",
    "D26": "2026-12-04T19:00:00",
    "D27": "2026-12-05T11:00:00",
    "D28": "2026-12-06T20:30:00",
    "D29": "2026-12-07T20:00:00",
    "D30": "2026-12-08T12:00:00",
}

BUFFER_TOKEN = os.environ.get("BUFFER_API_KEY")
CHANNEL_ID = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
REPO_NAME = os.environ.get(
    "GITHUB_REPOSITORY", "swaltnuscord-sketch/steady-days-insta-aut"
)
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "schedule")

if not BUFFER_TOKEN or not CHANNEL_ID:
  print(
      "Error: Missing BUFFER_API_KEY or BUFFER_INSTAGRAM_CHANNEL_ID in secrets."
  )
  sys.exit(1)

published_ids = []
if os.path.exists(PUBLISHED_LEDGER):
  with open(PUBLISHED_LEDGER, "r", encoding="utf-8") as f:
    published_ids = json.load(f)

if not os.path.exists("staging") or not glob.glob(
    "staging/**/manifest_*.json", recursive=True
):
  os.makedirs("staging", exist_ok=True)
  subprocess.run(
      [
          sys.executable,
          "-m",
          "gdown",
          "--folder",
          GDRIVE_FOLDER_URL,
          "-O",
          "staging/",
      ],
      check=True,
  )

matches = glob.glob("staging/**/manifest_*.json", recursive=True)
if not matches:
  print("Error: No manifest_*.json found in Google Drive folder.")
  sys.exit(1)

now_et = datetime.now(ET_TZ).replace(tzinfo=None)
print(f"Current US Eastern Time: {now_et.isoformat()}")

due_posts = []
for path in matches:
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
  pid = data.get("post_id")
  if not pid or pid in published_ids:
    continue

  slot_str = data.get("scheduled_at_et") or CALENDAR_SLOTS_ET.get(pid)
  if slot_str:
    slot_dt = datetime.fromisoformat(slot_str)
    if now_et >= slot_dt:
      due_posts.append((slot_dt.isoformat(), path, data))
  elif EVENT_NAME == "workflow_dispatch":
    # Unscheduled EXTRA_* posts only run on manual workflow_dispatch
    due_posts.append((data.get("generated_at", ""), path, data))

if not due_posts:
  print("No calendar posts are due right now. Exiting cleanly.")
  sys.exit(0)

_, target_manifest, manifest = min(due_posts, key=lambda x: x[0])
post_id = manifest.get("post_id")
print(f"Publishing due post {post_id}: {manifest.get('title')}")

os.makedirs("docs/images", exist_ok=True)
staging_dir = os.path.dirname(target_manifest)
image_name = manifest.get("image_filename")
source_image = os.path.join(staging_dir, image_name)

if not image_name or not os.path.exists(source_image):
  print(f"Error: Expected image {source_image} not found.")
  sys.exit(1)

shutil.copyfile(source_image, os.path.join("docs/images", image_name))

user, repo = REPO_NAME.split("/")
public_image_url = (
    f"https://raw.githubusercontent.com/{user}/{repo}/main/docs/images/{image_name}"
)
print(f"Public image URL: {public_image_url}")

full_text = (
    f"{manifest.get('caption', '').strip()}\n\n{manifest.get('cta', '').strip()}\n\n{manifest.get('hashtags', '').strip()}"
    .strip()
)

mutation = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post { id text status }
    }
    ... on MutationError { message }
  }
}
"""

variables = {
    "input": {
        "channelId": CHANNEL_ID,
        "text": full_text,
        "schedulingType": "automatic",
        "mode": "shareNow",
        "assets": [{"image": {"url": public_image_url}}],
        "metadata": {"instagram": {"type": "post", "shouldShareToFeed": True}},
    }
}

response = requests.post(
    BUFFER_API_URL,
    json={"query": mutation, "variables": variables},
    headers={
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json",
    },
)

res_json = response.json()
print("Buffer Response:\n", json.dumps(res_json, indent=2))

if "errors" in res_json or "message" in res_json.get("data", {}).get(
    "createPost", {}
):
  print("Buffer failed to create post.")
  sys.exit(1)

published_ids.append(post_id)
with open(PUBLISHED_LEDGER, "w", encoding="utf-8") as f:
  json.dump(published_ids, f, indent=2)
  f.write("\n")

print(f"Post {post_id} published and recorded in {PUBLISHED_LEDGER}!")
