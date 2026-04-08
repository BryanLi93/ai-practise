from fastapi import FastAPI, status, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas import ModelResponse, Provider, ModelCreate, ModelUpdate
from database import get_db, init_db
import crud

app = FastAPI()
init_db()

# 列表
@app.get('/models', response_model=list[ModelResponse])
def list_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_models(db, skip, limit)

# 查询列表
@app.get('/models/search', response_model=list[ModelResponse])
def list_models_filtered(provider: Provider, db: Session = Depends(get_db)):
    return crud.search_by_provider(db, provider)

# 详情
@app.get('/models/{model_id}', response_model=ModelResponse)
def detail_model(model_id: int, db: Session = Depends(get_db)):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return model

# 新增
@app.post('/models', status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
def create_model(model: ModelCreate, db: Session = Depends(get_db)):
    return crud.append(db, model)

# 更新
@app.put('/models/{model_id}', response_model=ModelResponse)
def update_model(model_id: int, model_info: ModelCreate, db: Session = Depends(get_db)):
    model = crud.update(db, model_id, model_info)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model
    

# 部分更新
@app.patch('/models/{model_id}', response_model=ModelResponse)
def patch_model(model_id: int, model_info: ModelUpdate, db: Session = Depends(get_db)):
    model = crud.update(db, model_id, model_info)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

# 删除
@app.delete('/models/{model_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int, db: Session = Depends(get_db)):
    if not crud.delete(db, model_id):
        raise HTTPException(status_code=404, detail="Model not found")