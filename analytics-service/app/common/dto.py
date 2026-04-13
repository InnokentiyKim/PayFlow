import uuid

from pydantic import BaseModel, ConfigDict


class BaseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BaseRequestDTO(BaseDTO): ...


class BaseResponseDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True)

    id: int | uuid.UUID
