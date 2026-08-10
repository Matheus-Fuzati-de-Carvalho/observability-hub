from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from observability_hub.api.v1 import catalog, projects
from observability_hub.core.bigquery import get_client
from observability_hub.core.exceptions import (
    DatasetNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TableNotFoundError,
)

app = FastAPI()

app.include_router(projects.router)
app.include_router(catalog.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ProjectAccessDeniedError)
def handle_project_access_denied(request: Request, exc: ProjectAccessDeniedError) -> JSONResponse:
    # A SA de fix é a do próprio ambiente em execução (dev ou prod), nunca
    # hardcoded — client.project reflete o projeto ADC do runtime atual.
    runtime_project = get_client().project
    sa_email = f"backend-run@{runtime_project}.iam.gserviceaccount.com"
    return JSONResponse(
        status_code=403,
        content={
            "error": "access_denied",
            "message": "A service account do Hub não tem acesso a este projeto.",
            "fix": (
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                "--role='roles/bigquery.metadataViewer'"
            ),
        },
    )


@app.exception_handler(ProjectNotFoundError)
def handle_project_not_found(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "project_not_found",
            "message": f"Projeto '{exc.project_id}' não encontrado ou não existe.",
        },
    )


@app.exception_handler(DatasetNotFoundError)
def handle_dataset_not_found(request: Request, exc: DatasetNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "dataset_not_found", "message": str(exc)},
    )


@app.exception_handler(TableNotFoundError)
def handle_table_not_found(request: Request, exc: TableNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "table_not_found", "message": str(exc)},
    )
