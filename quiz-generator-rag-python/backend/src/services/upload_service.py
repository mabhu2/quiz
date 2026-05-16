import os
from fastapi import UploadFile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_upload(file: UploadFile) -> str:
    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
    return dest
