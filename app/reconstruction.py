import os
import hashlib
from app.database import get_connection
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s — %(levelname)s — %(message)s')
logger = logging.getLogger(__name__)

RECONSTRUCTED_PATH = "reconstructed"


def calculate_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_and_verify_chunk(chunk_path: str, expected_checksum: str) -> bytes:
    with open(chunk_path, "rb") as f:
        data = f.read()

    actual_checksum = calculate_checksum(data)

    if actual_checksum != expected_checksum:
        raise ValueError(f"Checksum mismatch — data corrupted at {chunk_path}")

    return data


def reconstruct_file(file_id: int) -> str:
    os.makedirs(RECONSTRUCTED_PATH, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get primary chunks with checksums
        cur.execute(
            """
            SELECT chunk_index, node_path, checksum
            FROM chunks
            WHERE file_id = %s AND is_replica = FALSE
            ORDER BY chunk_index ASC
            """,
            (file_id,)
        )
        primary_chunks = cur.fetchall()

        if not primary_chunks:
            return None

        # Get replica chunks as fallback
        cur.execute(
            """
            SELECT chunk_index, node_path, checksum
            FROM chunks
            WHERE file_id = %s AND is_replica = TRUE
            ORDER BY chunk_index ASC
            """,
            (file_id,)
        )
        replica_chunks = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        output_path = os.path.join(
            RECONSTRUCTED_PATH,
            f"file_{file_id}_reconstructed.bin"
        )

        with open(output_path, "wb") as output_file:
            for chunk_index, primary_node_path, checksum in primary_chunks:
                chunk_name = f"file_{file_id}_chunk_{chunk_index}.bin"
                primary_path = os.path.join(primary_node_path, chunk_name)

                chunk_data = None

                # Try primary first
                if os.path.exists(primary_path):
                    try:
                        chunk_data = read_and_verify_chunk(primary_path, checksum)
                        logger.info(f"Chunk {chunk_index} — verified from primary")
                    except ValueError:
                        logger.warning(f"Chunk {chunk_index} — primary corrupted, trying replica")

                # Fall back to replica if primary missing or corrupted
                if chunk_data is None and chunk_index in replica_chunks:
                    replica_node_path, replica_checksum = replica_chunks[chunk_index]
                    replica_path = os.path.join(replica_node_path, chunk_name)

                    if os.path.exists(replica_path):
                        try:
                            chunk_data = read_and_verify_chunk(replica_path, replica_checksum)
                            logger.info(f"Chunk {chunk_index} — verified from replica")
                        except ValueError:
                            logger.error(f"Chunk {chunk_index} — replica also corrupted")

                if chunk_data is None:
                    raise FileNotFoundError(
                        f"Chunk {chunk_index} — unrecoverable, both copies missing or corrupted"
                    )

                output_file.write(chunk_data)

        return output_path

    except Exception as e:
        raise e
    finally:
        cur.close()
        conn.close()