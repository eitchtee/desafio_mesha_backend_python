import csv
import os
import tempfile
from ast import literal_eval
from io import StringIO
from typing import List
import datetime

from starlette.background import BackgroundTask

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

app = FastAPI()


def cleanup(temp_file):
    """
    Limpa arquivos temporários por meio de um BackgroundTask
    """
    os.remove(temp_file)


class CreateObra(BaseModel):
    """
    Modelo do Pydantic para envio de informações no corpo do request
    """
    titulo: str
    editora: str
    foto: str
    autores: List[str]


class Obra(BaseModel):
    """
    Modelo do Pydantic para criação da obra com os campos necessários e que não deveriam ser modificados pelo usuário (id, updated_at, created_at)
    """
    titulo: str
    editora: str
    foto: str
    autores: List[str]
    id: int
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime


class Obras:
    """
    Classe para armazenar e gerenciar obras. Poderia ser substituida por um ORM.
    """
    def __init__(self):
        self._obras = []
        self._current_id = len(self._obras)

    def append(self, obra: CreateObra):
        self._current_id += 1
        result = Obra(**obra.dict(), id=self._current_id, updated_at=datetime.datetime.utcnow())
        self._obras.append(result)
        return result

    def update(self, obra_id: int, updated_obra: CreateObra):
        # Retorna  o index do item que detém o id desejado
        matching_obra_index = next((i for i, item in enumerate(self._obras) if item.id == obra_id), None)

        if matching_obra_index is not None:
            self._obras[matching_obra_index] = Obra(**updated_obra.dict(),
                                                    created_at=self._obras[matching_obra_index].created_at,
                                                    updated_at=datetime.datetime.utcnow(),
                                                    id=self._obras[matching_obra_index].id)

            return self._obras[matching_obra_index]
        else:
            return None

    def delete(self, obra_id):
        # Retorna  o index do item que detém o id desejado
        matching_obra_index = next((i for i, item in enumerate(self._obras) if item.id == obra_id), None)

        return self._obras.pop(matching_obra_index) if matching_obra_index is not None else None

    def get_all(self):
        return self._obras

    def get_all_as_dict_filtered(self, filter_date = None):
        return [obra.dict() for obra in self._obras if not filter_date or obra.created_at >= filter_date]


obras = Obras()


@app.post("/obras", response_model=CreateObra)
async def post_obras(obra: CreateObra):
    """
    Adiciona uma obra ao banco de dados
    """
    return obras.append(obra)


@app.post("/upload-obras", response_model=List[Obra])
async def post_upload_obras(file: UploadFile = File(...)):
    """
    Importa os dados de um arquivo .csv com as colunas: titulo, editora, foto, autores. Ignora todas as outras colunas.
    """
    file = StringIO(file.file.read().decode('utf-8'))

    try:
        results = []
        for row in csv.DictReader(file, skipinitialspace=True):
            results.append(
                obras.append(
                    CreateObra(
                            titulo=row['titulo'],
                            editora=row['editora'],
                            foto=row['foto'],
                            autores=literal_eval(row['autores'])
                    )))
    except KeyError:
        raise HTTPException(status_code=400, detail="CSV mal formatado!")

    return results


@app.get("/obras")
async def get_obras():
    """
    Retorna uma lista com todas as obras no banco de dados
    """
    return obras.get_all()


@app.get("/file-obras", response_class=FileResponse)
async def get_file_obras(data_inicial: datetime.datetime = None):
    """
    Gera um .csv com todos as entradas no banco de dados.
    Pode ser filtrado utilizando uma data em ISO 8601
    """

    obras_list = obras.get_all_as_dict_filtered(filter_date=data_inicial)
    if not obras_list:
        raise HTTPException(status_code=404, detail="Nenhuma obra para exportar!")
    else:
        with tempfile.NamedTemporaryFile(mode="w", encoding='utf8', newline='', delete=False) as f:
            fc = csv.DictWriter(f,
                                fieldnames=obras_list[0].keys(),)
            fc.writeheader()
            fc.writerows(obras_list)

        return FileResponse(f.name,
                            media_type="text/csv",
                            filename="obras.csv",
                            background=BackgroundTask(cleanup, f.name))


@app.put("/obras/{update_id}")
async def put_obras(update_id: int, updated_obra: CreateObra):
    """
    Atualiza uma obra do banco de dados com base no seu respectivo id
    """

    response = obras.update(update_id, updated_obra)

    if response is None:
        raise HTTPException(status_code=404, detail="Obra não encontrada!")

    return response


@app.delete("/obras/{delete_id}")
async def post_upload_obras(delete_id: int):
    """
    Apaga uma obra do banco de dados com base no seu respectivo id
    """

    response = obras.delete(delete_id)

    if response is None:
        raise HTTPException(status_code=404, detail="Obra não encontrada!")

    return response


