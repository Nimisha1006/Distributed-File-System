# Distributed File Storage System

A backend system that stores files reliably across multiple nodes by splitting them into chunks, replicating each chunk, and verifying data integrity using checksums. Built to simulate real-world distributed storage systems like Amazon S3 and Google Drive.

> "Storage is easy. Failure is the real problem."

## Architecture

```
    Client (HTTP)
      │
      ▼
┌─────────────────────────┐
│   FastAPI (main.py)     │
│   coordinator + routing │
└────────┬────────┬───────┘
         │        │
         ▼        ▼
┌──────────────┐  ┌──────────────────────────┐
│  PostgreSQL  │  │  Storage Layer           │
│  files       │  │  node_1  node_2  node_3  │
│  chunks      │  │  · primary + replica     │
│  · node_path │  │  · SHA-256 verified      │
│  · checksum  │  └──────────────────────────┘
│  · is_replica│
└──────────────┘

Reconstruction: DB → read primary → verify checksum
              → fallback to replica if corrupted
              → merge chunks → original file
```


## Key Features

- **Chunk-based storage** — files split into fixed-size chunks distributed across nodes using round-robin placement
- **Replication** — every chunk stored on 2 different nodes (primary + replica)
- **SHA-256 integrity verification** — checksum calculated on upload, verified on every read
- **Automatic failover** — if primary chunk is missing or corrupted, system falls back to replica silently
- **Persistent metadata** — PostgreSQL tracks all file and chunk state, survives server restarts
- **ACID transactions** — failed uploads roll back cleanly, no partial state left in DB

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Storage | Local filesystem (simulated nodes) |
| Integrity | SHA-256 (hashlib) |
| Driver | psycopg2 |

---

## Project Structure
Distributed-File-System/
├── app/
│   ├── main.py          # FastAPI routes
│   ├── metadata.py      # DB operations for files and chunks
│   ├── storage.py       # Physical chunk storage and replication
│   ├── reconstruction.py # File reconstruction with integrity checks
│   └── database.py      # PostgreSQL connection
├── storage/
│   ├── node_1/          # Simulated storage node
│   ├── node_2/          # Simulated storage node
│   └── node_3/          # Simulated storage node
├── reconstructed/       # Reconstructed output files
├── test_upload.py       # End-to-end test script
└── README.md

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /files | Register a new file |
| GET | /files | List all files |
| GET | /files/{file_id} | Get file metadata and chunk locations |
| POST | /files/{file_id}/chunks/{chunk_index} | Upload a chunk |
| POST | /files/{file_id}/reconstruct | Reconstruct file from chunks |

---

## How It Works

### Upload Flow
1. Client registers file — gets back a file_id
2. Client uploads each chunk individually
3. Each chunk is stored on 2 different nodes (primary + replica)
4. SHA-256 checksum calculated and stored in PostgreSQL
5. When all chunks arrive, file status automatically changes to COMPLETE

### Reconstruction Flow
1. System queries PostgreSQL for ordered chunk locations
2. For each chunk, reads from primary node and verifies checksum
3. If primary is missing or corrupted, falls back to replica
4. Chunks merged in order into reconstructed output file
5. If both copies unrecoverable, explicit error raised

### Fault Tolerance Matrix

| Scenario | System Response |
|---|---|
| Node completely down | Falls back to replica |
| Chunk file missing | Falls back to replica |
| Chunk file corrupted | Detected via SHA-256, falls back to replica |
| Both copies missing | Explicit FileNotFoundError |
| Both copies corrupted | Explicit FileNotFoundError |

---

## Setup

```bash
# Clone the repo
git clone https://github.com/Nimisha1006/Distributed-File-System.git
cd Distributed-File-System

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install fastapi uvicorn psycopg2-binary

# Set up PostgreSQL
# Create database: distributed_storage
# Run schema from schema.sql

# Start server
uvicorn app.main:app --reload

# Run test
python test_upload.py
```

---

## Known Limitations & Future Improvements

- **Re-replication** — when a failed node recovers, missing chunks are not automatically rebuilt. Would require a background health-check service.
- **Client-side chunking** — currently chunking is done manually or via test script. A proper CLI client would handle splitting automatically.
- **Consistent hashing** — current round-robin placement means adding a new node requires reshuffling chunks. Consistent hashing would minimize redistribution.
- **Leader election** — metadata service is a single point of failure. A production system would use Raft or Paxos for coordinator election.

---

## Design Decisions

**Why PostgreSQL over NoSQL?**
Metadata has strict relational structure — files have chunks, chunks belong to files. Foreign keys and CASCADE deletes maintain consistency automatically. NoSQL would require building those guarantees manually.

**Why SHA-256 over MD5?**
MD5 has known collision vulnerabilities. SHA-256 is collision-resistant and standard for data integrity in production systems.

**Why 2 replicas over 3?**
With only 3 nodes, a third replica would land on the same node as the primary — defeating the purpose. Replication factor should scale with node count.
