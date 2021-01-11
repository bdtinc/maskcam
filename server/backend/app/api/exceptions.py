from fastapi import HTTPException


class NoItemFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=404,
            detail="No item was found for the provided ID",
        )


class ItemAlreadyExist(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=500,
            detail="An instance with the same id already exist",
        )


class GenericException(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=500,
            detail=f"An error occurred: \n{message}",
        )
