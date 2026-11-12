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

# Step 1: Download files from Google Drive
os.makedirs("staging", exist_ok=True)
download_cmd = [
    sys.executable,
    "-m",
    "gdown",
    "--folder",
    GDRIVE_FOLDER_URL,
    "-O",
    "staging/",
]
print("Fetching staged files from Google Drive...")
subprocess.run(download_cmd, check=True)

# Step 2: Locate and read the manifest with the latest generated_at timestamp
matches = glob.glob("staging/**/manifest_D*.json", recursive=True)
if not matches:
  matches = glob.glob("staging/**/manifest*.json", recursive=True)
if not matches:
  print("Error: No manifest found in Google Drive folder.")
  sys.exit(1)

manifests = []
for path in matches:
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
    manifests.append((data.get("generated_at", ""), path, data))

_, newest_manifest, manifest = max(manifests, key=lambda x: x[0])
print(
    f"Using manifest: {newest_manifest} (generated_at:"
    f" {manifest.get('generated_at')})"
)
print(f"Staging Post {manifest.get('post_id')}: {manifest.get('title')}")

# Step 3: Use the exact image_filename listed in the manifest
os.makedirs("docs/images", exist_ok=True)
staging_dir = os.path.dirname(newest_manifest)
image_name = manifest.get("image_filename")

if not image_name:
  print("Error: image_filename missing in manifest.")
  sys.exit(1)

source_image = os.path.join(staging_dir, image_name)
if not os.path.exists(source_image):
  print(f"Error: Expected image {source_image} not found.")
  sys.exit(1)

dest_image = os.path.join("docs/images", image_name)
shutil.copyfile(source_image, dest_image)

user, repo = REPO_NAME.split("/")
public_image_url = (
    f"https://raw.githubusercontent.com/{user}/{repo}/main/docs/images/{image_name}"
)
print(f"Public image URL: {public_image_url}")

# Step 4: Dispatch via Buffer GraphQL schema
caption = manifest.get("caption", "").strip()
cta = manifest.get("cta", "").strip()
hashtags = manifest.get("hashtags", "").strip()
full_text = f"{caption}\n\n{cta}\n\n{hashtags}".strip()

mutation = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        text
        status
      }
    }
    ... on MutationError {
      message
    }
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

if "errors" in res_json:
  print("GraphQL Error:", res_json["errors"])
  sys.exit(1)

post_result = res_json.get("data", {}).get("createPost", {})
if "message" in post_result:
  print("Buffer Mutation Error:", post_result["message"])
  sys.exit(1)

print("Post created successfully in Buffer!")
