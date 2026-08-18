from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from observability_hub.api.v1 import (
    access,
    access_requests,
    admin,
    auth,
    catalog,
    favorites,
    finops,
    freshness,
    history,
    lineage,
    pii,
    profiling,
    projects,
    quality,
    storage,
)
from observability_hub.core.bigquery import get_client
from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    AccessRequestNotFoundError,
    AdminAccessRequiredError,
    DatasetNotFoundError,
    InvalidDateColumnError,
    InvalidSamplePercentError,
    InvalidSessionError,
    LastAdminLockoutError,
    LoggingAccessDeniedError,
    OAuthEmailNotAllowedError,
    OAuthExchangeError,
    OAuthStateMismatchError,
    PiiScanTimeoutError,
    ProfilingTimeoutError,
    ProjectAccessDeniedError,
    ProjectNotAuthorizedError,
    ProjectNotFoundError,
    StorageAccessDeniedError,
    TableNotFoundError,
    TableNotPartitionedError,
)

app = FastAPI()

# Frontend roda em outra origem (Vite dev server local, ou outro serviço
# Cloud Run em prod) — sem isso todo fetch do browser falha no preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(catalog.router)
app.include_router(freshness.router)
app.include_router(profiling.router)
app.include_router(favorites.router)
app.include_router(history.router)
app.include_router(quality.router)
app.include_router(lineage.router)
app.include_router(pii.router)
app.include_router(access.router)
app.include_router(finops.router)
app.include_router(admin.router)
app.include_router(access_requests.router)
app.include_router(storage.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ProjectAccessDeniedError)
def handle_project_access_denied(request: Request, exc: ProjectAccessDeniedError) -> JSONResponse:
    # A SA de fix é a do próprio ambiente em execução (dev ou prod), nunca
    # hardcoded — client.project reflete o projeto ADC do runtime atual.
    runtime_project = get_client().project
    sa_email = f"backend-run@{runtime_project}.iam.gserviceaccount.com"
    # As três roles cobrem os dois modos de acesso que os domínios usam:
    # metadataViewer + jobUser dão conta de INFORMATION_SCHEMA (catalog,
    # freshness, discover_regions); dataViewer é o que profiling precisa a
    # mais pra rodar query real (mesmo um dry run) contra dados de tabela —
    # nenhuma das duas primeiras cobre isso. A exceção não carrega qual
    # permissão faltou especificamente, então sugerimos as três de uma vez;
    # add-iam-policy-binding é idempotente, rodar as três é seguro mesmo
    # quando só uma estava faltando.
    roles = ["bigquery.metadataViewer", "bigquery.jobUser", "bigquery.dataViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "access_denied",
            "message": "A service account do Hub não tem acesso a este projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
        },
    )


@app.exception_handler(LoggingAccessDeniedError)
def handle_logging_access_denied(request: Request, exc: LoggingAccessDeniedError) -> JSONResponse:
    runtime_project = get_client().project
    sa_email = f"backend-run@{runtime_project}.iam.gserviceaccount.com"
    # logging.viewer sozinho basta pra não estourar Forbidden, mas Data
    # Access audit logs (onde vive o jobCompletedEvent que lineage lê) só
    # ficam visíveis via API com logging.privateLogViewer também — sem essa
    # segunda role a chamada não falha, só retorna sempre vazio (ver aviso
    # estático em domains/lineage/service.py). Sugerimos as duas de uma vez,
    # mesmo padrão de ProjectAccessDeniedError.
    roles = ["logging.viewer", "logging.privateLogViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "logging_access_denied",
            "message": "A service account do Hub não tem acesso aos audit logs deste projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
        },
    )


@app.exception_handler(StorageAccessDeniedError)
def handle_storage_access_denied(request: Request, exc: StorageAccessDeniedError) -> JSONResponse:
    runtime_project = get_client().project
    sa_email = f"backend-run@{runtime_project}.iam.gserviceaccount.com"
    # roles/storage.objectViewer sozinha NÃO cobre storage.buckets.list/get
    # (só storage.objects.*) — confirmado em dev 2026-08-17 (403 mesmo com
    # a role concedida). list_buckets() precisa de storage.bucketViewer
    # também; a exceção não distingue qual das duas faltou, então sugerimos
    # as duas de uma vez, mesmo padrão de ProjectAccessDeniedError/
    # LoggingAccessDeniedError. Ver docs/specs/storage.md seção 8.
    roles = ["storage.bucketViewer", "storage.objectViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "storage_access_denied",
            "message": "A service account do Hub não tem acesso ao Cloud Storage deste projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
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


@app.exception_handler(TableNotPartitionedError)
def handle_table_not_partitioned(request: Request, exc: TableNotPartitionedError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "table_not_partitioned", "message": str(exc)},
    )


@app.exception_handler(InvalidSamplePercentError)
def handle_invalid_sample_percent(request: Request, exc: InvalidSamplePercentError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_sample_percent", "message": str(exc)},
    )


@app.exception_handler(InvalidDateColumnError)
def handle_invalid_date_column(request: Request, exc: InvalidDateColumnError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_date_column",
            "message": str(exc),
            "available_date_columns": exc.available_columns,
        },
    )


@app.exception_handler(ProfilingTimeoutError)
def handle_profiling_timeout(request: Request, exc: ProfilingTimeoutError) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"error": "profiling_timeout", "message": str(exc)},
    )


@app.exception_handler(PiiScanTimeoutError)
def handle_pii_scan_timeout(request: Request, exc: PiiScanTimeoutError) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"error": "pii_scan_timeout", "message": str(exc)},
    )


@app.exception_handler(OAuthStateMismatchError)
def handle_oauth_state_mismatch(request: Request, exc: OAuthStateMismatchError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "oauth_state_mismatch", "message": str(exc)},
    )


@app.exception_handler(OAuthExchangeError)
def handle_oauth_exchange_error(request: Request, exc: OAuthExchangeError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": "oauth_exchange_failed", "message": str(exc)},
    )


@app.exception_handler(OAuthEmailNotAllowedError)
def handle_oauth_email_not_allowed(
    request: Request, exc: OAuthEmailNotAllowedError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "email_not_allowed", "message": str(exc)},
    )


@app.exception_handler(InvalidSessionError)
def handle_invalid_session(request: Request, exc: InvalidSessionError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "invalid_session", "message": str(exc)},
    )


@app.exception_handler(ProjectNotAuthorizedError)
def handle_project_not_authorized(request: Request, exc: ProjectNotAuthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "project_not_authorized", "message": str(exc)},
    )


@app.exception_handler(AdminAccessRequiredError)
def handle_admin_access_required(request: Request, exc: AdminAccessRequiredError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "admin_access_required", "message": str(exc)},
    )


@app.exception_handler(LastAdminLockoutError)
def handle_last_admin_lockout(request: Request, exc: LastAdminLockoutError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "last_admin_lockout", "message": str(exc)},
    )


@app.exception_handler(AccessRequestNotFoundError)
def handle_access_request_not_found(
    request: Request, exc: AccessRequestNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "access_request_not_found", "message": str(exc)},
    )
