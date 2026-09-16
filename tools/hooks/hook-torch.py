"""Override contrib hook-torch.py to prevent collecting torch submodules.

torch is excluded from the build (see ATC-Desk.spec `excludes`).
faster-whisper uses CTranslate2 (C++), not torch. This empty hook shadows
the contrib hook that would pull in torch -> tensorboard -> tensorflow.
"""
hiddenimports = []
