import threading
import time
import os
import speech_recognition as sr

from speaker import GTTSThread, is_speaking
from ai_response import get_chat_response
from school_data import get_school_answer_enhanced
import shared_state
from register_face import register_name
from alsa_error import no_alsa_error


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
        try:
            if self.microphone is None:
                target_index = None
                
                # Dynamic microphone finding
                print("\n[Auto-Config] Searching for USB Microphone...")
                try:
                    mics = sr.Microphone.list_microphone_names()
                    for i, name in enumerate(mics):
                        print(f"  Device {i}: {name}")
                        if "USB" in name and "Hardware" in name: # Prefer hardware direct
                             target_index = i
                             break
                    
                    if target_index is None:
                        for i, name in enumerate(mics):
                             if "USB" in name:
                                  target_index = i
                                  break
                except Exception as e:
                    print(f"  Error listing mics: {e}")

                if target_index is not None:
                     print(f"✅ Found USB Microphone at index {target_index}")
                else:
                     print("⚠️ No USB Mic found, trying default (index 4 or default)")
                     target_index = 4 # Fallback

                try:
                    with no_alsa_error():
                        self.microphone = sr.Microphone(device_index=target_index)
                except ImportError:
                     self.microphone = sr.Microphone(device_index=target_index)
            return True
        except Exception as e:
            print(f"[Microphone] Could not open microphone: {e}")
            return False

    def run(self) -> None:
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0  
        self.recognizer.non_speaking_duration = 0.5

        print("\n" + "=" * 50)
        print("🎤 VOICE RECOGNITION STARTED")
        print("=" * 50)
        print("Say 'OMNIS' or 'HELLO' followed by your question")
        print("=" * 50 + "\n")

        while not self.stop_event.is_set() and not self._open_microphone():
            time.sleep(1)

        while not self.stop_event.is_set():
            try:
                with self.microphone as source:
                    print("🔊 Adjusting for ambient noise...")
                    with no_alsa_error():
                        self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    if self.recognizer.energy_threshold < 100:
                         self.recognizer.energy_threshold = 100
                    print(f"   Noise level: {self.recognizer.energy_threshold}\n")

                    timeout_count = 0
                    while not self.stop_event.is_set():
                        if self.conversation_active:
                            print("👂 Listening (conversation mode)...")
                        else:
                            print("👂 Listening for 'OMNIS'...")

                        try:
                            # FEEDBACK LOOP FIX: Wait if speaker is playing
                            if is_speaking():
                                print("🔇 Speaker active, waiting...", end='\r')
                                time.sleep(0.5)
                                continue
                                 
                            with no_alsa_error():     
                                audio_data = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)

                            if is_speaking():
                                print("🔇 Discarding (speaker active)")
                                continue

                            print("🔄 Processing audio...")
                            text = self.recognizer.recognize_google(audio_data)
                            print(f"📝 Heard: '{text}'")

                            if getattr(shared_state, 'awaiting_name', False):
                                name_spoken = text.strip()
                                greetings = {'hello', 'hi', 'hey', 'thanks', 'thank you'}
                                norm = name_spoken.lower().strip()
                                if not name_spoken or norm in greetings or len(''.join(ch for ch in norm if ch.isalpha())) < 2:
                                    self.speaker.speak("I didn't catch a name.")
                                    shared_state.awaiting_name = False
                                    shared_state.awaiting_encoding = None
                                    shared_state.awaiting_face_image = None
                                    continue
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
                                    print("\n✅ WAKE WORD DETECTED!\n")
                                    self.speaker.speak("Yes, how can I help you?")
                                    self.conversation_active = True
                                else:
                                    print("\n💬 Follow-up question\n")

                                question = text_lower
                                for w in self.wake_words:
                                    question = question.replace(w, "")
                                question = question.strip()
                                
                                if question and len(question) >= 3:
                                    print(f"❓ Question: {question}\n")
                                    school_ans = get_school_answer_enhanced(question)
                                    if school_ans:
                                        print(f"🏫 School Response: {school_ans}\n")
                                        self.speaker.speak(school_ans)
                                    else:
                                        print("🤖 Getting AI response...")
                                        resp = get_chat_response(question)
                                        if isinstance(resp, dict) and 'choices' in resp:
                                            answer = resp['choices'][0]['message']['content']
                                            print(f"💬 AI Response: {answer}\n")
                                            self.speaker.speak(answer)
                                        else:
                                            self.speaker.speak("Sorry, I couldn't process that.")
                                    timeout_count = 0
                            else:
                                print("   (No wake word)\n")

                        except sr.WaitTimeoutError:
                            if self.conversation_active:
                                timeout_count += 1
                                if timeout_count >= 3:
                                    print("⏱️ Timeout - say 'OMNIS' to start again\n")
                                    self.conversation_active = False
                                    timeout_count = 0
                        except sr.UnknownValueError:
                            print("   (Didn't catch that)\n")
                        except sr.RequestError as ex:
                            print(f"❌ Speech error: {ex}\n")
                        except Exception as e:
                            print(f"❌ Error: {e}")
                            time.sleep(1)
            except Exception as e:
                print(f"❌ Microphone Error: {e}")
                time.sleep(2)
                
    def stop(self):
        self.stop_event.set()
        print("\n🛑 Voice recognition stopped\n")


if __name__ == '__main__':
    pass