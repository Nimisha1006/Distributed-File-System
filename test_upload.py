import requests

BASE_URL = "http://localhost:8000"

# 1. Create a test file
with open("test.txt", "w") as f:
    f.write("Hello this is a test file for my distributed file system!")

# 2. Read and split into chunks
with open("test.txt", "rb") as f:
    data = f.read()

chunk_size = 20  # 20 bytes per chunk
chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
total_chunks = len(chunks)

print(f"File split into {total_chunks} chunks")

# 3. Register the file
response = requests.post(f"{BASE_URL}/files", json={
    "filename": "test.txt",
    "size": len(data),
    "total_chunks": total_chunks
})
file_id = response.json()["id"]
print(f"File registered with id: {file_id}")

# 4. Upload each chunk
for i, chunk in enumerate(chunks):
    files = {"chunk": ("chunk", chunk, "application/octet-stream")}
    response = requests.post(
        f"{BASE_URL}/files/{file_id}/chunks/{i}",
        files=files
    )
    print(f"Chunk {i} uploaded — status: {response.json()['status']}")

# 5. Reconstruct
response = requests.post(f"{BASE_URL}/files/{file_id}/reconstruct")
print(f"Reconstructed at: {response.json()}")