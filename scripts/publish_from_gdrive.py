import glob
import json
import os
import shutil
import subprocess
import sys
import requests

FOLDER_ID = "1i5pSM8yPiWII02c6af3tD5tJSRs44Z_C"
GDRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
BUFFER_API_URL = "https://api.buffer.com"

BUFFER_TOKEN = os.environ.get("BUFFER_API_KEY")
CHANNEL_ID = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
REPO_NAME = os.environ.get(
    "GITHUB_REPOSITORY", "swaltnuscord-sketch/steady-days-insta-aut"
)

if not BUFFER_TOKEN or not CHANNEL_ID:
  print(
      "Error: Missing BUFFER_API_KEY or BUFFER_INSTAGRAM_CHANNEL_ID in secrets."
  )
  sys.exit(1)

# Step 1: Download all files currently in the public Google Drive folder
os.makedirs("staging", exist_ok=True)
download_cmd = [
    sys.executable,
    "-m",
    "gdown",
    "--folder",
    GDRIVE_FOLDER_URL,
    "-O",
    "staging/",
    "--remaining-ok",
]
print("Fetching staged files from Google Drive...")
subprocess.run(download_cmd, check=True)

# Step 2: Locate and read manifest.json
manifest_path = "staging/manifest.json"
if not os.path.exists(manifest_path):
  # Search subdirectories if gdown created a nested folder
  matches = glob.glob("staging/**/manifest.json", recursive=True)
  if matches:
    manifest_path = matches[0]
  else:
    print("Error: No manifest.json found in the Google Drive folder.")
    sys.exit(1)

with open(manifest_path, "r", encoding="utf-8") as f:
  manifest = json.load(f)

post_id = manifest.get("post_id", "Unknown")
title = manifest.get("title", "")
print(f"Staging Post {post_id}: {title}")

# Step 3: Find the image and copy to docs/images for GitHub Pages
os.makedirs("docs/images", exist_ok=True)
staging_dir = os.path.dirname(manifest_path)
image_files = (
    glob.glob(f"{staging_dir}/*.jpg")
    + glob.glob(f"{staging_dir}/*.jpeg")
    + glob.glob(f"{staging_dir}/*.png")
)

if not image_files:
  print("Error: No image file found in the staging folder.")
  sys.exit(1)

source_image = image_files[0]
image_name = os.path.basename(source_image)
dest_image = os.path.join("docs/images", image_name)
shutil.copyfile(source_image, dest_image)

user, repo = REPO_NAME.split("/")
public_image_url = f"https://{user}.github.io/{repo}/images/{image_name}"
print(f"Public GitHub Pages URL: {public_image_url}")

# Step 4: Dispatch to Buffer GraphQL API
caption = manifest.get("caption", "").strip()
cta = manifest.get("cta", "").strip()
hashtags = manifest.get("hashtags", "").strip()

full_text = f"{caption}\n\n{cta}\n\n{hashtags}".strip()

mutation = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    post {
      id
      status
    }
  }
}
"""

variables = {
    "input": {
        "channelId": CHANNEL_ID,
        "text": full_text,
        "assets": [{"type": "IMAGE", "url": public_image_url}],
        "schedulingType": "NOW",
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
print("Buffer Response:", json.dumps(res_json, indent=2))

if "errors" in res_json:
  print("Buffer returned errors, check your channel ID or permissions.")
  sys.exit(1)
