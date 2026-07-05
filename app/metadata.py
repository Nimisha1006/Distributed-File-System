from app.database import get_connection
from app.storage import store_chunk
from datetime import datetime

def create_file(filename: str, size: int, total_chunks: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO files (filename, size, status, total_chunks, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (filename, size, "UPLOADING", total_chunks, datetime.utcnow())
        )
        file_id = cur.fetchone()[0]
        conn.commit()
        return {
            "id": file_id,
            "filename": filename,
            "size": size,
            "status": "UPLOADING",
            "total_chunks": total_chunks
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def list_files():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, filename, size, status, total_chunks, created_at FROM files")
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "filename": r[1],
                "size": r[2],
                "status": r[3],
                "total_chunks": r[4],
                "created_at": str(r[5])
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()


def get_file(file_id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, filename, size, status, total_chunks, created_at FROM files WHERE id = %s",
            (file_id,)
        )
        r = cur.fetchone()
        if not r:
            return None

        cur.execute(
            "SELECT chunk_index, node_path FROM chunks WHERE file_id = %s",
            (file_id,)
        )
        chunks = {row[0]: row[1] for row in cur.fetchall()}

        return {
            "id": r[0],
            "filename": r[1],
            "size": r[2],
            "status": r[3],
            "total_chunks": r[4],
            "created_at": str(r[5]),
            "chunk_locations": chunks
        }
    finally:
        cur.close()
        conn.close()


def upload_chunk(file_id: int, chunk_index: int, data: bytes):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Check file exists
        cur.execute("SELECT total_chunks FROM files WHERE id = %s", (file_id,))
        row = cur.fetchone()
        if not row:
            return None
        total_chunks = row[0]

        # 2. Physically store the chunk
        result = store_chunk(file_id, chunk_index, data)

        # 3. Insert primary and replica chunk records into DB
        # 3. Insert primary and replica chunk records into DB with checksum
        cur.execute(
            """
            INSERT INTO chunks (file_id, chunk_index, node_path, is_replica, checksum)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_id, chunk_index, is_replica) DO NOTHING
            """,
            (file_id, chunk_index, result["primary_node"], False, result["checksum"])
        )
        cur.execute(
            """
            INSERT INTO chunks (file_id, chunk_index, node_path, is_replica, checksum)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_id, chunk_index, is_replica) DO NOTHING
            """,
            (file_id, chunk_index, result["replica_node"], True, result["checksum"])
        )

        # 4. Check if all chunks are uploaded
        cur.execute(
            "SELECT COUNT(*) FROM chunks WHERE file_id = %s AND is_replica = FALSE",
            (file_id,)
        )
        uploaded_count = cur.fetchone()[0]

        if uploaded_count == total_chunks:
            cur.execute(
                "UPDATE files SET status = %s WHERE id = %s",
                ("COMPLETE", file_id)
            )

        conn.commit()
        return get_file(file_id)

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()