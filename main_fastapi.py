from __future__ import annotations

from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from atc_cleaner import ATCCleaner

app = FastAPI(title="ATC Transcript Processing API")

# Khoi tao instance 1 lan duy nhat khi khoi chay server.
cleaner = ATCCleaner()


class ProcessRequest(BaseModel):
    raw_text: str


class BatchProcessRequest(BaseModel):
    transcripts: List[str]


@app.post("/api/v1/clean-text")
async def clean_single_text(data: ProcessRequest):
    cleaned = cleaner.clean(data.raw_text)
    return {"status": "success", "raw": data.raw_text, "cleaned": cleaned}


@app.post("/api/v1/clean-batch")
async def clean_batch_text(data: BatchProcessRequest):
    cleaned_list = cleaner.clean_batch(data.transcripts)
    return {"status": "success", "total": len(cleaned_list), "data": cleaned_list}
