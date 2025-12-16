import speech_recognition as sr
import os

print("Scanning for microphones...")
try:
    mics = sr.Microphone.list_microphone_names()
except Exception as e:
    print(f"Error listing mics: {e}")
    mics = []

usb_mic_index = None

print("\nAvailable Microphones:")
for i, mic_name in enumerate(mics):
    print(f"{i}: {mic_name}")
    # Look for common USB mic names
    if "USB" in mic_name or "Webcam" in mic_name or "plughw" in mic_name or "C-Media" in mic_name:
        usb_mic_index = i

# Default to index 1 if a USB one wasn't explicitly named (Pi's onboard audio is usually 0)
if usb_mic_index is None:
    if len(mics) > 1:
        usb_mic_index = 1
    else:
        usb_mic_index = 0

print(f"\n✅ Auto-Selected Microphone Index: {usb_mic_index}")

print("Updating sr_class.py...")
try:
    with open('sr_class.py', 'r') as f:
        content = f.read()

    # We need to replace ALL instances of sr.Microphone() with sr.Microphone(device_index=X)
    # But first, let's remove any previous patches to ensure a clean state
    # This regex-like replace is safer
    
    # Reset to default first to avoid double patching keys
    content = content.replace("device_index=", "")
    content = content.replace("sr.Microphone()", f"sr.Microphone(device_index={usb_mic_index})")
    
    # Fix potential double closing parenthesis if we messed up
    content = content.replace("))", ")")

    with open('sr_class.py', 'w') as f:
        f.write(content)
    print(f"✅ sr_class.py updated to use Device Index {usb_mic_index}")

except Exception as e:
    print(f"❌ Error updating file: {e}")
