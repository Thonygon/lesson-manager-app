import pandas as pd


ARCHIVED_STATUS = "archived"
ACTIVE_STATUS = "active"


def normalize_status(value, default: str = ACTIVE_STATUS) -> str:
    text = str(value or "").strip().lower()
    return text or str(default or ACTIVE_STATUS).strip().lower() or ACTIVE_STATUS


def is_archived_status(value) -> bool:
    return normalize_status(value) == ARCHIVED_STATUS


def truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def ensure_status_column(df: pd.DataFrame, *, status_col: str = "status", default: str = ACTIVE_STATUS) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=[status_col])
    out = df.copy()
    if status_col not in out.columns:
        out[status_col] = default
    out[status_col] = out[status_col].apply(lambda value: normalize_status(value, default=default))
    return out


def filter_archived_rows(
    df: pd.DataFrame,
    *,
    status_col: str = "status",
    default: str = ACTIVE_STATUS,
    include_archived: bool = False,
    archived_only: bool = False,
) -> pd.DataFrame:
    out = ensure_status_column(df, status_col=status_col, default=default)
    if archived_only:
        out = out[out[status_col] == ARCHIVED_STATUS].copy()
    elif not include_archived:
        out = out[out[status_col] != ARCHIVED_STATUS].copy()
    return out.reset_index(drop=True)
