"""Puts harness/ on sys.path, so a test run as `python3 tests/t_x.py` imports m64, inject, game, testlib."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
