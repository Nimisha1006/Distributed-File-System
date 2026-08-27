import requests

BASE_URL = "http://localhost:8000"

# 1. Create test file
with open("test.txt", "w") as f:
    f.write("Hello this is a test file for WAL recovery testing!")

with open("test.txt", "rb") as f:
    data = f.read()

chunk_size = 20
chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
total_chunks = len(chunks)

print(f"File split into {total_chunks} chunks")

# 2. Register file
response = requests.post(f"{BASE_URL}/files", json={
    "filename": "test_wal.txt",
    "size": len(data),
    "total_chunks": total_chunks
})
file_id = response.json()["id"]
print(f"File registered with id: {file_id}")

# 3. Upload only FIRST 2 chunks — simulate failure midway
print("\n--- Simulating partial upload (uploading 2 of 3 chunks) ---")
for i in range(2):
    files = {"chunk": ("chunk", chunks[i], "application/octet-stream")}
    response = requests.post(
        f"{BASE_URL}/files/{file_id}/chunks/{i}",
        files=files
    )
    print(f"Chunk {i} uploaded — status: {response.json()['status']}")

# 4. Check resume point
print("\n--- Checking resume point ---")
response = requests.get(f"{BASE_URL}/files/{file_id}/resume")
resume = response.json()
print(f"Completed chunks: {resume['completed_chunks']}")
print(f"Resume from chunk: {resume['resume_from']}")

# 5. Resume from where we left off
print("\n--- Resuming upload from chunk", resume['resume_from'], "---")
for i in range(resume['resume_from'], total_chunks):
    files = {"chunk": ("chunk", chunks[i], "application/octet-stream")}
    response = requests.post(
        f"{BASE_URL}/files/{file_id}/chunks/{i}",
        files=files
    )
    print(f"Chunk {i} uploaded — status: {response.json()['status']}")

# 6. Reconstruct
print("\n--- Reconstructing ---")
response = requests.post(f"{BASE_URL}/files/{file_id}/reconstruct")
print(f"Result: {response.json()['message']}")