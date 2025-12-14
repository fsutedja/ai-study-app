from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from auth import router as auth_router
from paths import router as paths_router
from nodes import router as nodes_router
from questions import router as questions_router
from nodes import progress_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(paths_router)
app.include_router(nodes_router)
app.include_router(questions_router)
app.include_router(progress_router)

@app.get("/")
def root():
    return {"message": "Backend is running"}