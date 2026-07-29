"""Present so pytest puts the repository root on sys.path.

Without it, `from services import ld_utils` only resolves when pytest happens
to be invoked from the repository root.
"""
