from backend.models import User


DEFAULT_TWIN_NAME = "Echo"


def resolve_twin_name(user: User) -> str:
    """Return a safe twin name without ever deriving it from user identity fields."""
    raw_name = (user.twin_name or "").strip()
    user_name = (user.name or "").strip()
    inherited_user_name = (
        raw_name
        and user_name
        and raw_name.casefold() == user_name.casefold()
        and not bool(user.twin_name_customized)
    )
    if not raw_name or inherited_user_name:
        user.twin_name = DEFAULT_TWIN_NAME
        return DEFAULT_TWIN_NAME
    return raw_name
