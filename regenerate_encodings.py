"""
Regenerate Face Encodings
This script deletes old encoding files and creates fresh encodings
based on the current images in the images/faces folder.
"""

import os
import cv2
import face_recognition
import pickle

def regenerate_encodings():
    print("=" * 50)
    print("REGENERATING FACE ENCODINGS")
    print("=" * 50)
    
    # Step 1: Delete old encoding files
    old_files = [
        'encoded_file.p',
        'images/encoded_file.p'
    ]
    
    for file in old_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"✓ Deleted old encoding file: {file}")
        else:
            print(f"  (File not found: {file})")
    
    print()
    
    # Step 2: Load current images from faces folder
    folderPath = r'images/faces'
    
    if not os.path.exists(folderPath):
        print(f"ERROR: Folder '{folderPath}' does not exist!")
        return
    
    PathList = os.listdir(folderPath)
    
    if not PathList:
        print(f"ERROR: No images found in '{folderPath}'!")
        return
    
    print(f"Found {len(PathList)} images in {folderPath}:")
    for path in PathList:
        print(f"  - {path}")
    
    print()
    
    # Step 3: Load images and extract IDs
    imgList = []
    studentIds = []
    
    for path in PathList:
        img_path = os.path.join(folderPath, path)
        img = cv2.imread(img_path)
        
        if img is None:
            print(f"WARNING: Could not read image: {path}")
            continue
        
        imgList.append(img)
        studentIds.append(path.split('.')[0])
    
    print(f"Successfully loaded {len(imgList)} images")
    print(f"Student IDs: {studentIds}")
    print()
    
    # Step 4: Generate encodings
    print("Encoding faces... (this may take a moment)")
    encode_list = []
    
    for i, img in enumerate(imgList):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(img_rgb)
        
        if len(encodings) == 0:
            print(f"WARNING: No face detected in {PathList[i]}")
            continue
        
        encode_list.append(encodings[0])
        print(f"  ✓ Encoded: {studentIds[i]}")
    
    print()
    
    # Step 5: Save new encoding files
    encode_list_known_with_ids = [encode_list, studentIds[:len(encode_list)]]
    
    # Save to both locations
    save_locations = [
        'encoded_file.p',
        'images/encoded_file.p'
    ]
    
    for location in save_locations:
        with open(location, 'wb') as f:
            pickle.dump(encode_list_known_with_ids, f)
        print(f"✓ Saved new encoding file: {location}")
    
    print()
    print("=" * 50)
    print("ENCODING REGENERATION COMPLETE!")
    print("=" * 50)
    print(f"Total faces encoded: {len(encode_list)}")
    print("You can now run your OMNIS robot with fresh encodings.")

if __name__ == '__main__':
    regenerate_encodings()
