from schemas import ModelCreate, ModelUpdate, Provider
from models import AIModel
from sqlalchemy.orm import Session
from sqlalchemy import select

def get_models(db: Session, skip: int = 0, limit: int = 100) -> list[AIModel]:
        stmt = select(AIModel).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())
def get_model(db: Session, id: int) -> AIModel | None:
    return db.get(AIModel, id)
def append(db: Session, model: ModelCreate):
    db_model = AIModel(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model

def update(db: Session, id: int, model_info: ModelUpdate | ModelCreate) -> AIModel | None:
    db_model = get_model(db, id)
    if not db_model:
         return None
    for key, value in model_info.model_dump(exclude_unset=True).items():
         setattr(db_model, key, value)
    db.commit()
    db.refresh(db_model)
    return db_model

def delete(db: Session, id: int):
    db_model = get_model(db, id)
    if not db_model:
         return False
    db.delete(db_model)
    db.commit()
    return True

def search_by_provider(db: Session, provider: Provider):
    stmt = select(AIModel).filter_by(provider=provider)
    return list(db.scalars(stmt).all())