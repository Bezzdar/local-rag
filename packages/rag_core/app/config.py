"""Конфигурация параметров и путей для backend-компонентов."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PARSING_PATH = os.path.join(DATA_DIR, "parsing")
NOTEBOOKS_PATH = os.path.join(DATA_DIR, "notebooks")
LOGS_PATH = os.path.join(DATA_DIR, "logs")
