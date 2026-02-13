from app.engine import get_library_folders, trigger_indexing

if __name__ == "__main__":
    for folder in get_library_folders():
        trigger_indexing(folder)
