import speech_recognition as sr
import os

print("="*60)
print("🔎 SCIENTIFIC MICROPHONE FINDER")
print("="*60)

try:
    mics = sr.Microphone.list_microphone_names()
except Exception as e:
    print(f"Error listing: {e}")
    mics = []

working_index = None

print(f"\nFound {len(mics)} potential devices. Testing each one...\n")

for i, name in enumerate(mics):
    print(f"Testing Index {i}: '{name}'...", end="", flush=True)
    try:
        # Try to open the mic with this index
        mic = sr.Microphone(device_index=i) 
        with mic as source:
            # Just try to listen for a split second to see if the stream opens
            # We use a tiny timeout to fail fast
            pass
        print(f" ✅ PASS! (Stream opened)")
        
        # If we successfully opened it, this is likely our winner
        # We prefer USB devices, but if we found one that opened, we take note
        if working_index is None:
            working_index = i
        
        # If it's explicitly a USB device, it updates our best guess
        if "USB" in name or "Webcam" in name or "C-Media" in name:
            working_index = i
            print("   (Preferred USB device found!)")

    except Exception as e:
        # Most devices (like HDMI) will fail here, which is normal
        error_msg = str(e)
        if "monitor" in error_msg or "output" in error_msg: 
             print(" ❌ Skipped (Output only)")
        else:
             print(f" ❌ FAILED")

print("\n" + "="*60)
if working_index is not None:
    print(f"🎉 WINNER: Use Index {working_index} ({mics[working_index]})")
    
    # Auto-update the file if found
    try:
        with open('sr_class.py', 'r') as f:
            content = f.read()
            
        import re
        # Smart replacement of device_index=...
        new_content = re.sub(r'device_index=\d+', f'device_index={working_index}', content)
        
        with open('sr_class.py', 'w') as f:
            f.write(new_content)
        print(f"✅ Automatically updated sr_class.py to index {working_index}")
        
    except Exception as e:
        print(f"Could not auto-update: {e}")
else:
    print("😭 FATAL: No working microphone input found on this Raspberry Pi.")
    print("Please check if your USB microphone is plugged in correctly.")
print("="*60)
