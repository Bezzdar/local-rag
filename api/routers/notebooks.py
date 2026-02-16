from fastapi import APIRouter, HTTPException

from ..schemas import CreateNotebookRequest, IndexStatus, Notebook, UpdateNotebookRequest
from ..store import store

router = APIRouter(prefix="/api")


@router.get("/notebooks", response_model=list[Notebook])
def list_notebooks() -> list[Notebook]:
    return list(store.notebooks.values())


@router.post("/notebooks", response_model=Notebook)
def create_notebook(payload: CreateNotebookRequest) -> Notebook:
    return store.create_notebook(payload.title)


@router.get("/notebooks/{notebook_id}", response_model=Notebook)
def get_notebook(notebook_id: str) -> Notebook:
    nb = store.notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return nb


@router.patch("/notebooks/{notebook_id}", response_model=Notebook)
def update_notebook(notebook_id: str, payload: UpdateNotebookRequest) -> Notebook:
    nb = store.notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    nb.title = payload.title
    return nb


@router.delete("/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str) -> None:
    if notebook_id not in store.notebooks:
        raise HTTPException(status_code=404, detail="Notebook not found")
    del store.notebooks[notebook_id]


@router.get("/notebooks/{notebook_id}/index/status", response_model=IndexStatus)
def get_index_status(notebook_id: str) -> IndexStatus:
    items = [s for s in store.sources.values() if s.notebook_id == notebook_id]
    return IndexStatus(
        total=len(items),
        indexed=sum(1 for s in items if s.status == "indexed"),
        indexing=sum(1 for s in items if s.status == "indexing"),
        failed=sum(1 for s in items if s.status == "failed"),
    )
