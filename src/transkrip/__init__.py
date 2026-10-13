import os

# Windows tanpa Developer Mode tidak bisa membuat symlink di cache Hugging Face; itu tidak masalah.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
