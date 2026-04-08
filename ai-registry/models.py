from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(20))
    input_per_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_per_1m: Mapped[float | None] = mapped_column(Float, nullable=True)