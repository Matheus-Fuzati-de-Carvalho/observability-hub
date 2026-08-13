"""Exceções compartilhadas do modelo de acesso cross-project (ADR-006).

Vivem em core/ porque são reusadas por qualquer domínio que consulte um
projeto BigQuery alvo informado pelo usuário (catalog hoje; freshness e
profiling depois), não são específicas do domínio catalog.
"""


class ProjectAccessDeniedError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado ao projeto '{project_id}'.")


class LoggingAccessDeniedError(Exception):
    """A SA de runtime não tem roles/logging.viewer no projeto alvo —
    levantada por domains/lineage (e futuramente domains/access) ao
    consultar audit logs via Cloud Logging."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado aos audit logs do projeto '{project_id}'.")


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Projeto '{project_id}' não encontrado ou não existe.")


class DatasetNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        super().__init__(f"Dataset '{dataset_id}' não encontrado no projeto '{project_id}'.")


class TableNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(f"Tabela '{table_id}' não encontrada em '{project_id}.{dataset_id}'.")


class TableNotPartitionedError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(f"Tabela '{table_id}' em '{project_id}.{dataset_id}' não é particionada.")


class InvalidSamplePercentError(Exception):
    def __init__(self, sample_percent: float) -> None:
        self.sample_percent = sample_percent
        super().__init__(f"sample_percent deve ser >= 1 (recebido: {sample_percent}).")


class InvalidDateColumnError(Exception):
    def __init__(self, date_column: str, available_columns: list[str]) -> None:
        self.date_column = date_column
        self.available_columns = available_columns
        super().__init__(
            f"Coluna de data '{date_column}' não existe ou não é do tipo DATE/DATETIME/"
            f"TIMESTAMP. Colunas de data disponíveis: {available_columns}."
        )


class ProfilingTimeoutError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(
            f"Profiling de '{project_id}.{dataset_id}.{table_id}' excedeu 60s. "
            "Reduza sample_percent e tente novamente."
        )


class OAuthStateMismatchError(Exception):
    """O cookie oauth_state (setado em /auth/login) não bate com o
    parâmetro state devolvido por /auth/callback — sinal de CSRF ou de
    cookie expirado/perdido entre as duas etapas."""

    def __init__(self) -> None:
        super().__init__("Parâmetro state inválido ou ausente — tente fazer login novamente.")


class OAuthExchangeError(Exception):
    """Falha na troca do authorization code pelo token/userinfo do Google
    (rede, code expirado/reutilizado, credenciais OAuth erradas)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Falha ao autenticar com o Google: {detail}")


class OAuthEmailNotAllowedError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"E-mail '{email}' não está na allowlist de acesso.")


class InvalidSessionError(Exception):
    """Cookie de sessão (JWT) ausente, expirado ou com assinatura
    inválida — levantado por core/auth.py::get_current_user, usado em
    todo endpoint que exige usuário autenticado."""

    def __init__(self) -> None:
        super().__init__("Sessão inválida ou expirada — faça login novamente.")
