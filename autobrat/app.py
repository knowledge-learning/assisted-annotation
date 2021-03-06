import uuid
import os
import random
import markdown
import jinja2
import yaml
import shutil
import collections
import logging

from pathlib import Path
from functools import lru_cache
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException

from autobrat.data import load_config, load_corpus, read_file, load_training_data
from autobrat.classifier import Model
from scripts.utils import Collection

app = FastAPI()

app.mount("/static", StaticFiles(directory="/data"), name="static")
app.models = {}


def get_model(corpus: str) -> Model:
    if corpus not in app.models:
        collection = load_training_data(corpus)
        model = Model(collection)
        model.train()
        app.models[corpus] = model

    return app.models[corpus]


@app.get("/{corpus}", response_class=HTMLResponse)
def index(corpus: str):
    config = load_config(corpus)
    readme = read_file(corpus, config["index"]["readme"])

    with open("/autobrat/templates/index.html") as fp:
        template = jinja2.Template(fp.read())

    return HTMLResponse(template.render(readme=markdown.markdown(readme), corpus=corpus))


@app.get("/{corpus}/annotate", response_class=HTMLResponse)
def annotate(corpus: str, pack: str = None):
    with open("/autobrat/templates/annotation.html") as fp:
        template = jinja2.Template(fp.read())

    return HTMLResponse(template.render(corpus=corpus, pack=pack or ""))


@app.post("/{corpus}/task/annotate/entities")
def task_annotate_entities(corpus: str, pack: str):
    model = get_model(corpus)
    text_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.txt"

    with open(text_path) as fp:
        sentences = [s.strip("\n") for s in fp.readlines()]

    collection = model.predict_entities(sentences)
    collection.dump(text_path, skip_empty_sentences=False)

    return {"reload": True}


@app.post("/{corpus}/task/annotate/relations")
def task_annotate_relations(corpus: str, pack: str):
    model = get_model(corpus)
    text_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.txt"

    collection = Collection().load(text_path)
    collection = model.predict_relations(collection)
    collection.dump(text_path, skip_empty_sentences=False)

    return {"reload": True}


@app.post("/{corpus}/task/annotate/all")
def task_annotate_all(corpus: str, pack: str):
    model = get_model(corpus)
    text_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.txt"

    with open(text_path) as fp:
        sentences = [s.strip("\n") for s in fp.readlines()]

    collection = model.predict(sentences)
    collection.dump(text_path, skip_empty_sentences=False)

    return {"reload": True}


@app.post("/{corpus}/task/clear/all")
def task_clear_all(corpus: str, pack: str):
    ann_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.ann"

    with open(ann_path, "w") as fp:
        pass

    return {"reload": True}


@app.post("/{corpus}/task/clear/relations")
def task_clear_all(corpus: str, pack: str):
    path = Path("/data") / corpus / "packs" / "open" / pack / "pack.txt"

    collection = Collection()
    collection.load(path)

    for sentence in collection.sentences:
        sentence.relations = []

    collection.dump(path)

    return {"reload": True}


@app.post("/{corpus}/pack/new")
def new_pack(corpus: str):
    return {"next_pack": ensure_pack(corpus)}


@app.post("/{corpus}/pack/submit")
def submit_pack(corpus: str, pack: str):
    check_pack(corpus, pack)
    get_model(corpus).train_async()

    return {"next_pack": ensure_pack(corpus)}


def check_pack(corpus, pack):
    pack_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.ann"
    text_path = pack_path.with_suffix(".txt")

    if not pack_path.exists():
        raise HTTPException(400, "The current pack doesn't exists.")

    with open(pack_path) as fp:
        for line in fp:
            break
        else:
            raise HTTPException(400, "The current pack doesn't have any annotation.")

    shutil.move(pack_path, Path("/data") / corpus / "packs" / "submitted" / (pack + ".ann"))
    shutil.move(text_path, Path("/data") / corpus / "packs" / "submitted" / (pack + ".txt"))
    shutil.rmtree(pack_path.parent)


def ensure_pack(corpus):
    config = load_config(corpus)
    pack = str(uuid.uuid4())
    pack_path = Path("/data") / corpus / "packs" / "open" / pack / "pack.txt"
    ann_path = pack_path.with_suffix(".ann")
    os.makedirs(pack_path.parent)

    model = get_model(corpus)
    pool = load_corpus(corpus)

    with open(pack_path, "w") as fp:
        for sentence in model.suggest(pool):
            fp.write(sentence + "\n")

    with open(ann_path, "w") as fp:
        pass

    os.chmod(pack_path.parent, 0o777)
    os.chmod(pack_path, 0o777)
    os.chmod(ann_path, 0o777)

    return pack
