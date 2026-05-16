from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.models.quiz_models import (
    QuizGenerationRequest,
    QuizResponse,
    QuizResult,
    QuizSubmission,
)
from src.services.rag_service import QuizGenerationError, RAGService
from src.services.upload_service import save_upload

router = APIRouter()

rag = RAGService()


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    path = await save_upload(file)
    return {"filename": file.filename, "path": path}


@router.post("/generate", response_model=QuizResponse)
async def generate_quiz(request: QuizGenerationRequest):
    try:
        return await rag.generate_quiz(request)
    except QuizGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        if "GROQ_API_KEY" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groq API key is not configured.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI quiz generation failed.",
        ) from exc


@router.post("/evaluate", response_model=QuizResult)
async def evaluate_quiz(submission: QuizSubmission):
    return await rag.evaluate_submission(submission)
