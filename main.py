import os
# Fix for gRPC fork issue on Raspberry Pi
os.environ['GRPC_POLL_STRATEGY'] = 'epoll1'

import pickle
import cv2
import numpy as np
import cvzone
import face_recognition
import time
from speaker import speak, is_speaking
from sr_class import SpeechRecognitionThread
import shared_state
from register_face import register_name

# Adapter to provide a .speak() method for the SpeechRecognitionThread
class SpeakerAdapter:
    def speak(self, text):
        speak(text)

speaker_adapter = SpeakerAdapter()

# Global variables
imgBackground = cv2.imread('Resources/background.png')
speech_thread = None
conversation_active = False  # Track if voice conversation is happening
last_seen = {}  # person_id -> last seen timestamp
GREETING_COOLDOWN = 5  # seconds between greetings for the same person
FACE_MATCH_TOLERANCE = float(os.environ.get('FACE_MATCH_TOLERANCE', '0.55'))
# Maximum faces to process per frame to bound CPU usage (helps low-power devices)
MAX_FACES = int(os.environ.get('FACE_MAX_FACES', '4'))

# Ensure shared_state starts cleared to avoid accidental registration from previous runs
try:
    shared_state.awaiting_name = False
    shared_state.awaiting_encoding = None
    shared_state.awaiting_face_image = None
except Exception:
    pass

# Load mode images
folderModePath = 'Resources/Modes'
modePathList = os.listdir(folderModePath)
imgModeList = []
for path in modePathList:
    imgModeList.append(cv2.imread(os.path.join(folderModePath, path)))

# Load face encodings
print("Loading Encoded File")
with open(r'images/encoded_file.p', 'rb') as f:
    encode_list_known_with_ids = pickle.load(f)
encode_list_known, studentIds = encode_list_known_with_ids
print(f"Loaded {len(studentIds)} people: {studentIds}")

cap = cv2.VideoCapture(0)
mode_type = 0
prev_known_people = set()
last_primary_person = None

try:
    while True:
        try:
            ret, img = cap.read()
            if not ret or img is None:
                print("Camera error -retrying...")
                time.sleep(1)
                continue

            # Prepare image for face detection
            imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
            
            # Detect faces and encodings (protect against expensive failures)
            try:
                face_current_frame = face_recognition.face_locations(imgS)
                # Limit number of faces we encode to bound CPU usage
                if face_current_frame and len(face_current_frame) > MAX_FACES:
                    if os.environ.get('OMNIS_DEBUG') == '1':
                        print(f"[DEBUG] Too many faces detected ({len(face_current_frame)}), limiting to {MAX_FACES}")
                    face_current_frame = face_current_frame[:MAX_FACES]
                encode_current_frame = face_recognition.face_encodings(imgS, face_current_frame)
            except Exception as e:
                # Log and continue to next frame
                if os.environ.get('OMNIS_DEBUG') == '1':
                    print(f"[DEBUG] Face processing error: {e}")
                face_current_frame = []
                encode_current_frame = []

            # Update background with current frame
            imgBackground[162:162+480, 55:55+640] = img
            imgBackground[44:44+633, 808:808+414] = imgModeList[mode_type]

            detected_person = None
            detected_location = None

            # Check each face detected. Collect known people in the frame so we can greet each one once.
            known_people_in_frame = set()
            first_match = None
            matched_people_info = []
            if face_current_frame:
                for encodeFace, faceLoc in zip(encode_current_frame, face_current_frame):
                    matches = face_recognition.compare_faces(encode_list_known, encodeFace, tolerance=FACE_MATCH_TOLERANCE)
                    face_distance = face_recognition.face_distance(encode_list_known, encodeFace)
                    match_index = np.argmin(face_distance)

                    # Debug: log which person was chosen for this face and the numeric distance
                    if os.environ.get('OMNIS_DEBUG') == '1':
                        try:
                            chosen = studentIds[match_index] if matches[match_index] else 'UNKNOWN'
                            print(f"[DEBUG] face match candidate: chosen={chosen} index={match_index} dist={face_distance[match_index]:.3f} matches={matches[match_index]}")
                        except Exception:
                            pass

                    if matches[match_index]:
                        person = studentIds[match_index]
                        known_people_in_frame.add(person)
                        # Compute area (in small-frame coords) to pick the frontmost person
                        y1f, x2f, y2f, x1f = faceLoc
                        area = max(0, (y2f - y1f)) * max(0, (x2f - x1f))
                        matched_people_info.append((person, faceLoc, area))
                        # Keep the first matched face for display
                        if first_match is None:
                            first_match = (person, faceLoc)
                    else:
                        # Keep unknown face for display if nobody known yet
                        if first_match is None:
                            first_match = ("Unknown", faceLoc)

                    # Debug: print face_distance values when requested
                    import os as _os
                    if _os.environ.get('OMNIS_DEBUG') == '1':
                        # Show numeric distances (smaller is better) and chosen index
                        try:
                            distances_str = ','.join([f"{d:.3f}" for d in face_distance])
                        except Exception:
                            distances_str = str(face_distance)
                        print(f"[DEBUG] face_distances=[{distances_str}] chosen_index={match_index} chosen_match={matches[match_index]}")

                if first_match:
                    detected_person, detected_location = first_match
                # Determine primary (frontmost) known person by largest detected face area
                primary_person = None
                if matched_people_info:
                    primary_person = max(matched_people_info, key=lambda t: t[2])[0]

            # Handle face display and greeting
            if detected_person:
                current_time = time.time()
                
                # Draw face box
                y1, x2, y2, x1 = detected_location
                y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
                
                if detected_person != "Unknown":
                    # KNOWN PERSON: Green box
                    bbox = (55+x1, 162+y1, x2 - x1, y2 - y1)
                    imgBackground = cvzone.cornerRect(imgBackground, bbox=bbox, rt=0)
                    mode_type = 1
                    
                    # Greeting logic - Don't greet during active conversation
                    is_in_conversation = False
                    if speech_thread and speech_thread.is_alive():
                        is_in_conversation = speech_thread.conversation_active
                        
                    if not is_in_conversation:
                        conversation_active = False
                        # Greet newly-arrived people immediately; for those already present, respect cooldown
                        new_people = known_people_in_frame - prev_known_people
                        # Greet newcomers first (always queue the greeting so it plays even if TTS is busy)
                        for person in new_people:
                            # Debug: why we will greet this person
                            if os.environ.get('OMNIS_DEBUG') == '1':
                                print(f"[DEBUG] greeting new person: {person}")
                            payload = f"Hello {person}! Welcome to MGM Model School robot."
                            speak(payload)
                            last_seen[person] = current_time

                        # For people who were already present, greet only if cooldown expired
                        existing_people = known_people_in_frame & prev_known_people
                        for person in existing_people:
                            last = last_seen.get(person, 0)
                            if (current_time - last) > GREETING_COOLDOWN:
                                if os.environ.get('OMNIS_DEBUG') == '1':
                                    print(f"[DEBUG] greeting existing person after cooldown: {person} last_seen={last} now={current_time}")
                                payload = f"Hello {person}! Welcome to MGM Model School robot."
                                speak(payload)
                                last_seen[person] = current_time

                        # Optional debug logging controlled by OMNIS_DEBUG environment variable
                        import os
                        if os.environ.get('OMNIS_DEBUG') == '1':
                            print(f"[DEBUG] known_people_in_frame={known_people_in_frame}")
                            print(f"[DEBUG] prev_known_people={prev_known_people}")
                            print(f"[DEBUG] new_people={new_people}")
                            print(f"[DEBUG] last_seen_snapshot={dict(last_seen)}")

                        # Greet primary person (frontmost) if they changed since last frame
                        if 'primary_person' in locals() and primary_person:
                            if os.environ.get('OMNIS_DEBUG') == '1':
                                print(f"[DEBUG] primary_person={primary_person} last_primary={last_primary_person}")
                            if primary_person != last_primary_person:
                                if os.environ.get('OMNIS_DEBUG') == '1':
                                    print(f"[DEBUG] greeting primary person: {primary_person}")
                                payload = f"Hello {primary_person}! Welcome to MGM Model School robot."
                                speak(payload)
                                last_seen[primary_person] = current_time
                                last_primary_person = primary_person
                        else:
                            last_primary_person = None

                        # Update prev_known_people for next frame
                        prev_known_people = set(known_people_in_frame)

                        # Start voice recognition thread only if mic is available and not running
                        if not (speech_thread and speech_thread.is_alive()):
                            try:
                                import speech_recognition as _sr
                                from alsa_error import no_alsa_error
                                try:
                                    with no_alsa_error():
                                        _sr.Microphone()
                                    mic_available = True
                                except Exception as _e:
                                    mic_available = False
                                    print(f"[Main] Microphone unavailable: {_e}")
                            except Exception as _e:
                                mic_available = False
                                print(f"[Main] Could not check microphone: {_e}")

                            if mic_available:
                                speech_thread = SpeechRecognitionThread(speaker_adapter)
                                speech_thread.daemon = True
                                speech_thread.start()
                
                    # Display student name
                    (w, h), _ = cv2.getTextSize(detected_person, cv2.FONT_HERSHEY_COMPLEX, 1, 1)
                    offset = (414 - w) / 2
                    cv2.putText(imgBackground, str(detected_person), (808 + int(offset), 445),
                               cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 50), 1)
                    
                    # Display student image
                    img_path = f'images/faces/{detected_person}.jpg'
                    if os.path.exists(img_path):
                        img_student = cv2.imread(img_path)
                        if img_student is not None:
                            img_student = cv2.resize(img_student, (216, 216))
                            imgBackground[175:175 + 216, 909:909 + 216] = img_student
                else:
                    # UNKNOWN PERSON: Red box
                    current_time = time.time()
                    # Fallback greeting for an unrecognized primary person (friendly prompt)
                    unknown_key = "UNKNOWN_FACE"
                    last_unknown = last_seen.get(unknown_key, 0)
                    if (current_time - last_unknown) > GREETING_COOLDOWN:
                        # Greet unknown/frontmost person once per cooldown window
                        payload = "Hello there!"
                        speak(payload)
                        last_seen[unknown_key] = current_time
                        last_primary_person = unknown_key
                        last_primary_person = unknown_key

                    cv2.rectangle(imgBackground, (55+x1, 162+y1), (55+x2, 162+y2), (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.putText(imgBackground, "Unknown", (55+x1, max(162+y1-10, 180)), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                    mode_type = 0
            else:
                # NO FACE DETECTED
                mode_type = 0

            # Display window
            cv2.imshow("Face Attendance", imgBackground)
            
            # Exit on 'q'
            if cv2.waitKey(1) == ord('q'):
                break
        except KeyboardInterrupt:
            print('\n[Main] Interrupted by user, shutting down gracefully...')
            break
        except Exception as e:
            print(f"[Main] Unhandled error in frame processing: {e}")
            # small sleep to avoid hot loop on persistent errors
            time.sleep(0.5)
            continue
finally:
    try:
        cap.release()
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
