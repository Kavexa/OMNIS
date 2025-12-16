import cv2
import face_recognition
import pickle
import numpy as np

print("="*50)
print("🧐 FACE RECOGNITION DIAGNOSTIC")
print("="*50)

# 1. Try to load encodings
try:
    print("Loading encoded_file.p...", end="")
    with open(r'encoded_file.p', 'rb') as f:
        encode_list_known_with_ids = pickle.load(f)
    known_encodings, known_names = encode_list_known_with_ids
    print(f" ✅ Success!")
    print(f"Known People: {known_names}")
except Exception as e:
    print(f"\n❌ Error loading file: {e}")
    print("Please run: python3 EncodeGenerator.py")
    exit()

# 2. Open Camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Critical: Could not open camera (Index 0)")
    exit()

print("\n📸 Camera active. Look at the camera!")
print("Press 'q' to quit.\n")

while True:
    ret, frame = cap.read()
    if not ret: continue

    # Resize for speed (match main.py logic)
    imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
    imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

    try:
        # Detect faces
        face_locs = face_recognition.face_locations(imgS)
        encodings = face_recognition.face_encodings(imgS, face_locs)

        if not face_locs:
            print(".", end="", flush=True)  # Print dot if no face
        
        for encoding, face_loc in zip(encodings, face_locs):
            # Calculate distances to ALL known faces
            distances = face_recognition.face_distance(known_encodings, encoding)
            match_index = np.argmin(distances)
            min_dist = distances[match_index]
            
            # Print detailed stats
            print(f"\n👤 Face Detected!")
            print(f"   Closest Match: {known_names[match_index]}")
            print(f"   Distance Score: {min_dist:.4f}  (Need < 0.55 to match)")
            
            # Visual indicator
            if min_dist < 0.55:
                print("   ✅ MATCH SUCCESS")
            else:
                print("   ❌ NO MATCH (Tolerance too strict?)")
                
            print("-" * 30)

    except Exception as e:
        print(f"Error: {e}")

    # Show video
    cv2.imshow("Debug Face", frame)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
