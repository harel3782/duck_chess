"""Pytest configuration for headless testing."""
import os
import sys

# Set headless display for pygame before any imports
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

# Initialize pygame in headless mode
try:
    import pygame
    pygame.init()
except Exception as e:
    print(f"Warning: Could not initialize pygame: {e}")

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
