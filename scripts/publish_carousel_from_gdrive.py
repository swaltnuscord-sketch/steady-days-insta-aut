from datetime import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo
import requests

TRIGGER_FILE = "staging/carousel_trigger.json"
PUBLISHED_LEDGER = "published.json"
BUFFER_API_URL = "https://api.buffer.com"
ET_TZ = ZoneInfo("America/New_York")

BUFFER_TOKEN = os.environ.get("BUFFER_API_KEY")
CHANNEL_ID = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
REPO_NAME = os.environ.get(
    "GITHUB_REPOSITORY", "swaltnuscord-sketch/steady-days-insta-aut"
)
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "schedule")


def main():
  if not BUFFER_TOKEN or not CHANNEL_ID:
    print(
        "Error: Missing BUFFER_API_KEY or BUFFER_INSTAGRAM_CHANNEL_ID in"
        " secrets."
    )
    sys.exit(1)

  if not os.path.exists(TRIGGER_FILE):
    print(f"No {TRIGGER_FILE} found. Exiting cleanly.")
    sys.exit(0)

  with open(TRIGGER_FILE, "r", encoding="utf-8") as f:
    trigger = json.load(f)

  manifest_url = trigger.get("manifest_direct_download_url")
  if not manifest_url:
    print("Error: manifest_direct_download_url missing in carousel_trigger.json.")
    sys.exit(1)

  resp = requests.get(manifest_url, allow_redirects=True, timeout=30)
  if not resp.ok:
    print(
        f"Error: Could not download manifest from {manifest_url}"
        f" ({resp.status_code})"
    )
    sys.exit(1)

  manifest = resp.json()
  post_id = manifest.get("post_id")
  if not post_id:
    print("Error: post_id missing in manifest.")
    sys.exit(1)

  published_ids = []
  if os.path.exists(PUBLISHED_LEDGER):
    with open(PUBLISHED_LEDGER, "r", encoding="utf-8") as f:
      published_ids = json.load(f)

  if post_id in published_ids:
    print(f"Post {post_id} is already in {PUBLISHED_LEDGER}. Exiting cleanly.")
    sys.exit(0)

  now_et = datetime.now(ET_TZ).replace(tzinfo=None)
  scheduled_str = manifest.get("scheduled_at_et")
  print(f"Current US Eastern Time: {now_et.isoformat()}")
  print(f"Post {post_id} scheduled_at_et: {scheduled_str} (event: {EVENT_NAME})")

  if scheduled_str:
    scheduled_dt = datetime.fromisoformat(scheduled_str)
    if now_et < scheduled_dt:
      print(
          f"Post {post_id} is not due yet ({scheduled_dt.isoformat()} ET)."
          " Pages are built and images are staged. Exiting cleanly."
      )
      sys.exit(0)

  image_filenames = manifest.get("image_filenames", [])
  if len(image_filenames) != 5:
    print(f"Error: Expected 5 image_filenames, got {len(image_filenames)}")
    sys.exit(1)

  user, repo = REPO_NAME.split("/")
  assets = []
  for fname in image_filenames:
    pages_url = f"https://{user}.github.io/{repo}/images/{fname}"
    raw_url = (
        f"https://raw.githubusercontent.com/{user}/{repo}/main/docs/images/{fname}"
    )
    # Prefer the built GitHub Pages URL when live; fall back to raw URL if needed
    check = requests.head(pages_url, allow_redirects=True, timeout=10)
    public_url = pages_url if check.ok else raw_url
    print(f"Using image URL for {fname}: {public_url}")
    assets.append({"image": {"url": public_url}})

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
          "assets": assets,
          "metadata": {
              "instagram": {"type": "post", "shouldShareToFeed": True}
          },
      }
  }

  buf_resp = requests.post(
      BUFFER_API_URL,
      json={"query": mutation, "variables": variables},
      headers={
          "Authorization": f"Bearer {BUFFER_TOKEN}",
          "Content-Type": "application/json",
      },
      timeout=30,
  )
  res_json = buf_resp.json()
  print("Buffer Response:\n", json.dumps(res_json, indent=2))

  if "errors" in res_json or "message" in res_json.get("data", {}).get(
      "createPost", {}
  ):
    print("Buffer failed to create carousel post.")
    sys.exit(1)

  published_ids.append(post_id)
  with open(PUBLISHED_LEDGER, "w", encoding="utf-8") as f:
    json.dump(published_ids, f, indent=2)
    f.write("\n")

  print(f"Carousel {post_id} published and recorded in {PUBLISHED_LEDGER}!")


if __name__ == "__main__":
  main()
