from core.i18n import t
from core.state import (
    get_current_user_id, with_owner,
    _set_logged_in_user, _clear_logged_in_user, _user_to_dict,
    PROFILE_SUBJECT_OPTIONS, PROFILE_STAGE_OPTIONS, PROFILE_TEACH_LANG_OPTIONS,
    PROFILE_DURATION_OPTIONS, PROFILE_TIMEZONE_OPTIONS, PROFILE_COUNTRY_OPTIONS,
)
from core.timezone import (
    LOCAL_TZ, UTC_TZ, DEFAULT_TZ_NAME,
    detect_browser_timezone, get_app_tz_name, get_app_tz, now_local, today_local,
)
from core.navigation import (
    PAGES, PAGE_KEYS,
    _set_query, _get_qp,
    go_to, home_go, page_header,
    init_navigation_defaults,
)
from core.database import (
    get_sb, load_table, load_students, ensure_student, norm_student,
    clear_app_caches, register_cache,
    apply_auth_session, get_user_display_name,
    get_profile_avatar_url, save_profile_avatar_url,
    load_profile_row, upsert_profile_row,
    add_class, add_payment, delete_row,
    normalize_latest_package, update_student_profile,
    update_payment_row, update_class_row,
)
