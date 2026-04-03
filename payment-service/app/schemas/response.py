from datetime import datetime

from app.common.dto import BaseResponseDTO
from app.common.enums import PaymentStatusEnum


class PaymentResponseDTO(BaseResponseDTO):
    status: PaymentStatusEnum
    created_at: datetime
    updated_at: datetime
