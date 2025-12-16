import pickle
print("Testing encoding file...")
with open('images/encoded_file.p', 'rb') as f:
    encode_list_known_with_ids = pickle.load(f)
encode_list_known, studentIds = encode_list_known_with_ids
print(f"Loaded {len(studentIds)} people: {studentIds}")
