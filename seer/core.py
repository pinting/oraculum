import seer

schema: str = ""

VOCABULARY_PATH: str = "../vocabulary.tiktoken"
EOS_ID: int = 1

def set_schema(_schema: str):
    global schema
    
    schema = _schema

def get_schema() -> str:
    return schema

def load_vocabulary(path: str) -> bytes:
    with open(path, "r", encoding="utf-8") as f:
        data: str = f.read()

    return data.encode("utf-8")

def init_engine(vocabulary_data: bytes, eos_id: int, schema: str) -> None:
    result: int = seer.init_vocabulary(vocabulary_data, eos_id)

    if result != 0:
        raise RuntimeError("Failed to initialize vocabulary")

    result = seer.init_schema(schema.encode("utf-8"))

    if result != 0:
        raise RuntimeError("Failed to initialize schema")
