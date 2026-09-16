"""Override contrib hook-tensorboard.py to prevent collecting tensorboard submodules.

tensorboard is excluded from the build (see ATC-Desk.spec `excludes`).
This empty hook shadows the contrib hook that would pull in tensorboard -> tensorflow.
"""
hiddenimports = []
