from pydantic import BaseModel


class JsonRpcRequest(BaseModel):
    jsonrpc: str
    id: str | int
    method: str
    params: dict 


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int 
    result: dict


class JsonRpcError(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None
    
    class ErrorType(BaseModel):
        code: int
        message: str

    error: ErrorType
    data: dict | None = None
    
    def add_error_data(self, data: dict):
        if self.data is None:
            self.data = {}
        self.data.update(data)
        return self

    @classmethod
    def error_from_code(cls, code, id=None):
        match code:
            case -32600:
                return cls(id=id, error=cls.ErrorType(code=code, message="Invalid request"))
            case -32602:
                return cls(id=id, error=cls.ErrorType(code=code, message="Invalid params"))
            case -32700:
                return cls(id=id, error=cls.ErrorType(code=code, message="Internal error"))
            case _:
                return cls(id=id, error=cls.ErrorType(code=code, message="Unknown error"))

