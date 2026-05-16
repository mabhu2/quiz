"""Convenience runner to start the backend from project root.
This changes cwd into the backend folder and runs main.py there.
It also ensures the backend folder is added to sys.path so package imports work.
"""
import os
import sys
import runpy

BASE = os.path.dirname(__file__)
BACKEND_DIR = os.path.join(BASE, "quiz-generator-rag-python", "backend")
BACKEND_MAIN = os.path.join(BACKEND_DIR, "main.py")
# Ensure backend dir is on sys.path so `import src` works when running from project root
if BACKEND_DIR not in sys.path:
	sys.path.insert(0, BACKEND_DIR)

os.chdir(BACKEND_DIR)
runpy.run_path(BACKEND_MAIN, run_name="__main__")
