import os
import hashlib

BASE_STORAGE_PATH = "storage"

DATA_NODES = [
    os.path.join(BASE_STORAGE_PATH, "node_1"),
    os.path.join(BASE_STORAGE_PATH, "node_2"),
    os.path.join(BASE_STORAGE_PATH, "node_3"),
]


def ensure_nodes_exist():
    for node in DATA_NODES:
        os.makedirs(node, exist_ok=True)


def choose_primary_node(chunk_index: int) -> str:
    return DATA_NODES[chunk_index % len(DATA_NODES)]


def choose_replica_node(chunk_index: int) -> str:
    return DATA_NODES[(chunk_index + 1) % len(DATA_NODES)]


def calculate_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_chunk(file_id: int, chunk_index: int, data: bytes):
    ensure_nodes_exist()

    primary_node = choose_primary_node(chunk_index)
    replica_node = choose_replica_node(chunk_index)

    chunk_name = f"file_{file_id}_chunk_{chunk_index}.bin"

    # Store primary
    primary_path = os.path.join(primary_node, chunk_name)
    with open(primary_path, "wb") as f:
        f.write(data)

    # Store replica
    replica_path = os.path.join(replica_node, chunk_name)
    with open(replica_path, "wb") as f:
        f.write(data)

    # Calculate checksum once — same for both copies
    checksum = calculate_checksum(data)

    return {
        "primary_node": primary_node,
        "replica_node": replica_node,
        "checksum": checksum
    }


def get_chunk(file_id: int, chunk_index: int) -> bytes:
    primary_node = choose_primary_node(chunk_index)
    chunk_name = f"file_{file_id}_chunk_{chunk_index}.bin"
    chunk_path = os.path.join(primary_node, chunk_name)

    if not os.path.exists(chunk_path):
        return None

    with open(chunk_path, "rb") as f:
        return f.read()