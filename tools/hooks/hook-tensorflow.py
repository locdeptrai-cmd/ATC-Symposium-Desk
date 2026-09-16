"""Override contrib hook-tensorflow.py to prevent collecting tensorflow submodules.

tensorflow is excluded from the build (see ATC-Desk.spec `excludes`).
This empty hook shadows the contrib hook that calls collect_submodules('tensorflow'),
which triggers a slow and noisy import attempt that fails with a warning.
"""
# Intentionally empty: no hidden imports, no collection, no data files.
hiddenimports = []
