import sys

try:
    with open('sr_class.py', 'r') as f:
        content = f.read()

    # Increase timeout and phrase limits
    new_content = content.replace('timeout=2, phrase_time_limit=4', 'timeout=5, phrase_time_limit=10')

    # Add pause threshold
    if 'pause_threshold' not in new_content:
        new_content = new_content.replace(
            'self.recognizer.dynamic_energy_threshold = True',
            'self.recognizer.dynamic_energy_threshold = True\n        self.recognizer.pause_threshold = 1.2'
        )

    with open('sr_class.py', 'w') as f:
        f.write(new_content)
    
    print("✅ sr_class.py successfully updated!")

except Exception as e:
    print(f"❌ Error: {e}")
