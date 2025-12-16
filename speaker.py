import os
import threading
import time
import uuid
import pygame
from gtts import gTTS

# Shared state to check if speaker is active
_global_speaker_active = False
_last_spoken_time = 0

def is_speaking():
    return _global_speaker_active

def get_last_spoken_time():
    return _last_spoken_time

class GTTSThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = []
        self.lock = threading.Lock()
        self.running = True

    def run(self):
        global _global_speaker_active
        while self.running:
            text_to_speak = None
            
            self.lock.acquire()
            if self.queue:
                text_to_speak = self.queue.pop(0)
            self.lock.release()

            if text_to_speak:
                _global_speaker_active = True
                try:
                    # 1. Generate Audio file
                    filename = f"speak_{uuid.uuid4()}.mp3"
                    tts = gTTS(text=text_to_speak, lang='en', tld='com')
                    tts.save(filename)

                    # 2. Play Audio FORCEFULLY on Card 1 (USB Speaker)
                    # using 'plughw:1,0' is the safest way to talk to ALSA
                    os.system(f"mpg321 -a plughw:1,0 -q {filename}")
                    
                    # Cleanup
                    if os.path.exists(filename):
                        os.remove(filename)

                except Exception as e:
                    print(f"Speaker Error: {e}")
                finally:
                    _global_speaker_active = False
                    _last_spoken_time = time.time()
            else:
                time.sleep(0.1)

    def speak(self, text):
        self.lock.acquire()
        self.queue.append(text)
        self.lock.release()

    def stop(self):
        self.running = False

# Global helper for main.py
_global_speaker_thread = None

def init_speaker_thread():
    global _global_speaker_thread
    if _global_speaker_thread is None:
        _global_speaker_thread = GTTSThread()
        _global_speaker_thread.start()
    return _global_speaker_thread

def speak(text):
    """Global speak function called by main.py"""
    s = init_speaker_thread()
    s.speak(text)
