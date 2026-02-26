
import sys
import platform

print("Mocking platform...")
platform.machine = lambda: "AMD64"
platform.processor = lambda: "AMD64"
platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19041', 'SP0', 'Multiprocessor Free')

print("Importing edge_tts...")
try:
    import edge_tts
    print("Imported edge_tts successfully")
except Exception as e:
    print(f"Failed to import edge_tts: {e}")
except SystemExit:
    print("SystemExit caught")
except KeyboardInterrupt:
    print("KeyboardInterrupt caught")
