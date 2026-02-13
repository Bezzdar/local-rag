import sys
from app.engine import trigger_indexing

if __name__ == "__main__":
    folder = sys.argv[1]
    trigger_indexing(folder)
