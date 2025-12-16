import pickle
with open('images/encoded_file.p', 'rb') as f:
    encode_list_known_with_ids = pickle.load(f)
encode_list_known, studentIds = encode_list_known_with_ids
print(f"\n✅ Loaded {len(studentIds)} people:")
for i, name in enumerate(studentIds, 1):
    print(f"  {i}. {name}")
