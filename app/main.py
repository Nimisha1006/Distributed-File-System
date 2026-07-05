from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app import metadata
from fastapi import UploadFile, File
from app import storage
from app import reconstruction

app = FastAPI()


class FileCreateRequest(BaseModel):
    filename: str
    size: int
    total_chunks: int


@app.post("/files")
def register_file(request: FileCreateRequest):
    file = metadata.create_file(
        filename=request.filename,
        size=request.size,
        total_chunks=request.total_chunks
    )
    return file


@app.get("/files")
def list_all_files():
    return metadata.list_files()


@app.get("/files/{file_id}")
def get_file_info(file_id: int):
    file = metadata.get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@app.post("/files/{file_id}/chunks/{chunk_index}")
def upload_chunk(
    file_id: int,
    chunk_index: int,
    chunk: UploadFile = File(...)
):
    data = chunk.file.read()
    file = metadata.upload_chunk(file_id, chunk_index, data)

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return file

@app.post("/files/{file_id}/reconstruct")
def reconstruct(file_id: int):
    path = reconstruction.reconstruct_file(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="File or chunks not found")
    return {
        "message": "File reconstructed successfully",
        "path": path
    }