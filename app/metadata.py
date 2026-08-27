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
        # Check file exists
        cur.execute("SELECT total_chunks FROM files WHERE id = %s", (file_id,))
        row = cur.fetchone()
        if not row:
            return None
        total_chunks = row[0]

        # WAL step 1 — log IN_PROGRESS before doing anything
        cur.execute(
            """
            INSERT INTO upload_log (file_id, chunk_index, status)
            VALUES (%s, %s, 'IN_PROGRESS')
            ON CONFLICT (file_id, chunk_index) 
            DO UPDATE SET status = 'IN_PROGRESS', attempted_at = CURRENT_TIMESTAMP
            """,
            (file_id, chunk_index)
        )
        conn.commit()

        # WAL step 2 — physically store chunk + replicate
        result = store_chunk(file_id, chunk_index, data)

        # WAL step 3 — insert primary and replica into chunks table
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

        # WAL step 4 — mark COMPLETE in log
        cur.execute(
            """
            UPDATE upload_log 
            SET status = 'COMPLETE', completed_at = CURRENT_TIMESTAMP
            WHERE file_id = %s AND chunk_index = %s
            """,
            (file_id, chunk_index)
        )

        # Check if all chunks are done
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
        # WAL — mark FAILED so client knows this chunk needs retry
        try:
            cur.execute(
                """
                UPDATE upload_log 
                SET status = 'FAILED'
                WHERE file_id = %s AND chunk_index = %s
                """,
                (file_id, chunk_index)
            )
            conn.commit()
        except:
            pass
        raise e
    finally:
        cur.close()
        conn.close()

def get_resume_point(file_id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Get all completed chunks
        cur.execute(
            """
            SELECT chunk_index FROM upload_log
            WHERE file_id = %s AND status = 'COMPLETE'
            ORDER BY chunk_index ASC
            """,
            (file_id,)
        )
        completed = [row[0] for row in cur.fetchall()]

        # Get failed chunks that need retry
        cur.execute(
            """
            SELECT chunk_index FROM upload_log
            WHERE file_id = %s AND status = 'FAILED'
            ORDER BY chunk_index ASC
            """,
            (file_id,)
        )
        failed = [row[0] for row in cur.fetchall()]

        # Get total chunks expected
        cur.execute("SELECT total_chunks FROM files WHERE id = %s", (file_id,))
        row = cur.fetchone()
        if not row:
            return None
        total_chunks = row[0]

        next_chunk = len(completed)

        return {
            "file_id": file_id,
            "total_chunks": total_chunks,
            "completed_chunks": completed,
            "failed_chunks": failed,
            "next_chunk_to_upload": next_chunk,
            "resume_from": next_chunk
        }

    finally:
        cur.close()
        conn.close()