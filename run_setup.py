#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecom_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

# Now run the command
from ecom_backend.management.commands.setup_test_data import Command

cmd = Command()
cmd.stdout.write = print  # Redirect stdout
cmd.stderr.write = print  # Redirect stderr

# Create a style object
class Style:
    def SUCCESS(self, msg):
        return f"✓ {msg}"
    def WARNING(self, msg):
        return f"⚠ {msg}"

cmd.style = Style()

try:
    cmd.handle()
    print("\n✨ Database population completed successfully!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
