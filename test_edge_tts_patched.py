
import sys
import platform

# MONKEY PATCH: Fix broken WMI on user system
def mock_win32_ver(release='', version='', csd='', ptype=''):
    return ('10', '10.0.19041', 'SP0', 'Multiprocessor Free')

platform.win32_ver = mock_win32_ver

def mock_machine():
    return 'AMD64'

platform.machine = mock_machine
platform.processor = mock_machine

print("Importing edge_tts...")
import edge_tts
print("Imported edge_tts successfully")
