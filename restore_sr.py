import os

# CLEAN VERSION of sr_class.py with:
# 1. Correct syntax (fixed the parenthesis error)
# 2. Hardcoded Microphone Index 1 (based on your scan)
# 3. Enhanced hearing settings (timeout=10, pause_threshold=1.0)

FRESH_SR_CLASS = r'''import threading
import time
import os
import speech_recognition as sr

from speaker import GTTSThread, is_speaking
from ai_response import get_chat_response
from school_data import get_school_answer_enhanced
import shared_state
from register_face import register_name


class SpeechRecognitionThread(threading.Thread):
    def __init__(self, speaker: GTTSThread):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.speaker = speaker
        self.verbose = True
        self.conversation_active = False
        self.microphone = None
        self.conversation_timeout = 15
        
        env_wake = os.environ.get('WAKE_WORDS')
        if env_wake:
            self.wake_words = [w.strip().lower() for w in env_wake.split(',') if w.strip()]
        else:
            self.wake_words = ['omnis', 'hello']
        self.recognizer = sr.Recognizer()

    def _open_microphone(self) -> bool:
        """Attempt to open the microphone with specific device index."""
        try:
            if self.microphone is None:
                try:
                    from alsa_error import no_alsa_error
                    with no_alsa_error():
                        # Explicitly use device_index=1 as found by diagnostic
                        self.microphone = sr.Microphone(device_index=1)
                except ImportError:
                     self.microphone = sr.Microphone(device_index=1)
            return True
        except Exception as e:
            print(f"[Microphone] Could not open microphone: {e}")
            return False

    def run(self) -> None:
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0  
        self.recognizer.non_speaking_duration = 0.5

        if self.verbose:
            print("\n" + "=" * 50)
            print("🎤 VOICE RECOGNITION RESTORED")
            print("=" * 50)
            print("Say 'OMNIS' followed by your question")
            print("=" * 50 + "\n")

        while not self.stop_event.is_set() and not self._open_microphone():
            time.sleep(1)

        while not self.stop_event.is_set():
            try:
                with self.microphone as source:
                    if self.verbose:
                        print("🔊 Adjusting for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    
                    # Force sensible floor for threshold
                    if self.recognizer.energy_threshold < 100:
                         self.recognizer.energy_threshold = 100
                    
                    if self.verbose:
                        print(f"   Noise level set to: {self.recognizer.energy_threshold}\n")

                    timeout_count = 0
                    while not self.stop_event.is_set():
                        if self.verbose:
                            if self.conversation_active:
                                print("👂 Listening (conversation mode)...")
                            else:
                                print("👂 Listening for 'OMNIS'...")

                        try:
                            if is_speaking():
                                time.sleep(0.5)
                                continue

                            # Listening settings
                            audio_data = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)

                            if self.verbose:
                                print("🔄 Processing audio...")
                                
                            text = self.recognizer.recognize_google(audio_data)
                            
                            if self.verbose:
                                print(f"📝 Heard: '{text}'")

                            if getattr(shared_state, 'awaiting_name', False):
                                name_spoken = text.strip()
                                greetings = {'hello', 'hi', 'hey', 'thanks', 'thank you'}
                                norm = name_spoken.lower().strip()
                                # THIS IS THE LINE THAT WAS BROKEN - FIXED NOW
                                if not name_spoken or norm in greetings or len(''.join(ch for ch in norm if ch.isalpha())) < 2:
                                    print(f"[Register] Ignored unlikely name input: '{name_spoken}'")
                                    self.speaker.speak("I didn't catch a name.")
                                    shared_state.awaiting_name = False
                                    shared_state.awaiting_encoding = None
                                    shared_state.awaiting_face_image = None
                                    continue

                                print(f"[Register] Heard name: '{name_spoken}' - registering...")
                                enc = getattr(shared_state, 'awaiting_encoding', None)
                                img = getattr(shared_state, 'awaiting_face_image', None)
                                ok = register_name(name_spoken, enc, img)
                                if ok:
                                    self.speaker.speak(f"Thanks {name_spoken}, I will remember you.")
                                else:
                                    self.speaker.speak("Sorry, I couldn't save your name.")
                                shared_state.awaiting_name = False
                                shared_state.awaiting_encoding = None
                                shared_state.awaiting_face_image = None
                                continue

                            text_lower = text.lower()
                            tokens = text_lower.split()
                            
                            if self.conversation_active:
                                has_wake_word = False
                            else:
                                has_wake_word = any(w in tokens for w in self.wake_words)

                            if has_wake_word or self.conversation_active:
                                if has_wake_word:
                                    print("\n==========\n✅ WAKE WORD DETECTED!\n==========\n")
                                    self.speaker.speak("Yes?")
                                    self.conversation_active = True
                                else:
                                    print("\n💬 Follow-up question\n")

                                question = text_lower
                                for w in self.wake_words:
                                    question = question.replace(w, "")
                                question = question.strip()
                                if question:
                                    print(f"❓ Question: {question}\n")
                                    if len(question.strip()) >= 3:
                                        print("🏫 Checking School Database...")
                                        school_ans = get_school_answer_enhanced(question)
                                        if school_ans:
                                            print(f"\n🏫 School Response: {school_ans}\n")
                                            self.speaker.speak(school_ans)
                                        else:
                                            print("🤖 Getting AI response...")
                                            resp = get_chat_response(question)
                                            if isinstance(resp, dict) and 'choices' in resp:
                                                answer = resp['choices'][0]['message']['content']
                                                print(f"\n💬 AI Response: {answer}\n")
                                                self.speaker.speak(answer)
                                            else:
                                                self.speaker.speak("Sorry, I couldn't process that.")
                                    else:
                                        self.speaker.speak("Please ask a specific question.")

                                    timeout_count = 0
                                else:
                                    if self.verbose:
                                        print("⏳ Waiting for your question...")
                            else:
                                if self.verbose:
                                    print("   (No wake word detected)\n")

                        except sr.WaitTimeoutError:
                            if self.conversation_active:
                                timeout_count += 1
                                if timeout_count >= 3:
                                    print("⏱️  Listening timeout\n")
                                    self.conversation_active = False
                                    timeout_count = 0
                        except sr.UnknownValueError:
                            if self.verbose:
                                print("   (Didn't catch that)\n")
                        except sr.RequestError as ex:
                            print(f"❌ Speech recognition error: {ex}")
                        except Exception as e:
                            print(f"❌ Unexpected error in loop: {e}")
                            time.sleep(1)
            except Exception as e:
                print(f"❌ Critical Microphone Error: {e}")
                
    def stop(self):
        self.stop_event.set()
        if self.verbose:
            print("\n🛑 Voice recognition stopped\n")

if __name__ == '__main__':
    pass
'''

with open('sr_class.py', 'w') as f:
    f.write(FRESH_SR_CLASS)

print("✅ sr_class.py RESTORED and FIXED!")
