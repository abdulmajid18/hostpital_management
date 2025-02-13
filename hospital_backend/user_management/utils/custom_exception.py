from rest_framework import status
from rest_framework.exceptions import APIException


class CustomException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A server error occurred."
    default_code = "error"

    def __init__(self, detail=None, code=None, status_code=None):
        if isinstance(detail, str):
            detail = {"error": detail}
        super().__init__(detail, code)
        if status_code is not None:
            self.status_code = status_code
