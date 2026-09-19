"""Universal search API."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Machine, Error, Shop

search_bp = Blueprint("search", __name__, url_prefix="/api")


def _serialize_error(e, visible_machines=None):
    """Serialize error with shop-scoped machine names.

    Visible machines = union of:
      - M2M linkage (machine_errors)
      - Auto-paired via error.machine_name pattern
    """
    import re

    if visible_machines is None:
        # 1) M2M-linked machines (shop-scoped)
        m2m_machines = list(e.machines)
        if not current_user.is_admin:
            m2m_machines = [
                m for m in m2m_machines
                if m.shop_id == current_user.shop_id
            ]

        # 2) Auto-paired machines (via error.machine_name)
        auto_machines = []
        if e.machine_name:
            pattern = str(e.machine_name).lower()

            mq = Machine.query.filter(Machine.status != Machine.STATUS_ARCHIVED)
            if not current_user.is_admin:
                if current_user.shop_id is None:
                    mq = mq.filter(db.false())
                else:
                    mq = mq.filter(Machine.shop_id == current_user.shop_id)

            for m in mq.all():
                text = (str(m.machine_code or "") + " " + str(m.machine_name or "")).lower()
                tokens = [
                    t for t in re.split(r"[\s_\-./]+", text)
                    if len(t) >= 3
                ]
                if any(tok in pattern for tok in tokens):
                    auto_machines.append(m)

        # 3) Union (dedupe by id)
        seen = set()
        visible_machines = []
        for m in m2m_machines + auto_machines:
            if m.id in seen:
                continue
            seen.add(m.id)
            visible_machines.append(m)

    # Photos — up to 5 preview URLs
    photos = []
    try:
        for img in (e.images or [])[:5]:
            path = getattr(img, "image_path", None) or ""
            # Normalize: image_path looks like "errors/ERROR_1/xxx.jpg"
            # Public URL = /uploads/errors/ERROR_1/xxx.jpg
            if path:
                if path.startswith("/"):
                    url = path
                elif path.startswith("uploads/"):
                    url = "/" + path
                else:
                    url = "/uploads/" + path
            else:
                url = ""
            if url:
                photos.append({
                    "id": img.id,
                    "url": url,
                    "caption": getattr(img, "caption", None),
                })
    except Exception:
        photos = []

    return {
        **e.to_dict(),
        "machine_count": len(visible_machines),
        "photos": photos,
        "photo_count": len(e.images) if hasattr(e, "images") else len(photos),
        "machines": [
            {
                "id": m.id,
                "machine_code": m.machine_code,
                "machine_name": m.machine_name,
                "shop_code": m.shop.shop_code if m.shop else None,
            }
            for m in visible_machines[:5]
        ],
    }


def _serialize_machine(m):
    """Serialize machine with related error summary."""
    visible_errors = list(m.errors) if current_user.is_admin else list(m.errors)
    return {
        **m.to_dict(),
        "shop_code": m.shop.shop_code if m.shop else None,
        "error_count": len(visible_errors),
        "errors": [
            {
                "id": e.id,
                "error_code": e.error_code,
                "error_name": e.error_name,
                "category": e.category or "ERROR",
            }
            for e in visible_errors[:5]
        ],
    }


def _serialize_machine_with_related(m, related_error_ids):
    """Serialize machine with errors from M2M + auto-pair.

    `related_error_ids` is the union of:
      - errors linked via M2M (machine_errors)
      - errors matched via error.machine_name pattern
    Only errors applicable to THIS machine are included.
    """
    import re
    from ..models import Error as _Error

    # Start with M2M linkage
    m2m_errors = list(m.errors) if hasattr(m, "errors") else []

    # Auto-pair — find errors whose machine_name matches this machine's tokens
    def _tokens(text):
        if not text:
            return []
        return [
            t.lower() for t in re.split(r"[\s_\-./]+", str(text))
            if len(t) >= 3
        ]

    m_tokens = set(_tokens(m.machine_code) + _tokens(m.machine_name))
    auto_errors = []
    if m_tokens:
        # Only fetch errors we haven't already got from M2M
        m2m_ids = {e.id for e in m2m_errors}
        candidates = (
            _Error.query
            .filter(
                _Error.status != _Error.STATUS_ARCHIVED,
                _Error.machine_name.isnot(None),
                _Error.machine_name != "",
            )
            .all()
        )
        for e in candidates:
            if e.id in m2m_ids:
                continue
            pattern = str(e.machine_name).lower()
            if any(tok in pattern for tok in m_tokens):
                auto_errors.append(e)

    # Combined
    seen = set()
    combined = []
    for e in m2m_errors + auto_errors:
        if e.id in seen:
            continue
        seen.add(e.id)
        combined.append(e)

    return {
        **m.to_dict(),
        "shop_code": m.shop.shop_code if m.shop else None,
        "error_count": len(combined),
        "errors": [
            {
                "id": e.id,
                "error_code": e.error_code,
                "error_name": e.error_name,
                "category": e.category or "ERROR",
            }
            for e in combined[:5]
        ],
    }


def _machine_query_for_user(query, user):
    q = Machine.query.join(Shop)
    if not user.is_admin:
        if user.shop_id is None:
            return q.filter(db.false())
        q = q.filter(Machine.shop_id == user.shop_id)

    if query:
        # Split into words for multi-word search
        words = [w for w in query.split() if len(w) > 0]
        conditions = [
            Machine.machine_code.ilike(f"%{query}%"),
            Machine.machine_name.ilike(f"%{query}%"),
            Machine.description.ilike(f"%{query}%"),
        ]
        for w in words:
            wlike = f"%{w}%"
            conditions.append(db.or_(
                Machine.machine_code.ilike(wlike),
                Machine.machine_name.ilike(wlike),
                Machine.description.ilike(wlike),
            ))
        q = q.filter(db.or_(*conditions))

    q = q.filter(Machine.status != Machine.STATUS_ARCHIVED)
    return q


def _error_query(query):
    q = Error.query
    if query:
        words = [w for w in query.split() if len(w) > 0]
        conditions = [
            Error.error_code.ilike(f"%{query}%"),
            Error.error_name.ilike(f"%{query}%"),
            Error.error_fix.ilike(f"%{query}%"),
            Error.explanation.ilike(f"%{query}%"),
            Error.machine_name.ilike(f"%{query}%"),
        ]
        for w in words:
            wlike = f"%{w}%"
            conditions.append(db.or_(
                Error.error_code.ilike(wlike),
                Error.error_name.ilike(wlike),
                Error.error_fix.ilike(wlike),
                Error.explanation.ilike(wlike),
                Error.machine_name.ilike(wlike),
            ))
        q = q.filter(db.or_(*conditions))

    q = q.filter(Error.status != Error.STATUS_ARCHIVED)
    return q


def _auto_pair_errors(machines, errors):
    """Auto-match machines ↔ errors by keyword overlap.

    No M2M linkage required. Uses error.machine_name field.

    Match rule:
      - For each machine, tokenize machine_code + machine_name
      - For each error, check if any machine token (>=3 chars) appears
        in error.machine_name (case-insensitive)
      - Return {machine_id: [error, ...]}
    """
    import re

    def _tokens(text):
        if not text:
            return []
        return [
            t.lower() for t in re.split(r"[\s_\-./]+", str(text))
            if len(t) >= 3
        ]

    pairs = {}
    for m in machines:
        m_tokens = set(_tokens(m.machine_code) + _tokens(m.machine_name))
        if not m_tokens:
            pairs[m.id] = []
            continue

        matched = []
        for e in errors:
            if not e.machine_name:
                continue
            e_pattern = str(e.machine_name).lower()
            # any machine token appears in error.machine_name
            if any(tok in e_pattern for tok in m_tokens):
                matched.append(e)
        pairs[m.id] = matched

    return pairs


@search_bp.route("/search")
@login_required
def search():
    query = (request.args.get("q") or "").strip()
    search_type = (request.args.get("type") or "all").lower()
    limit = min(max(request.args.get("limit", 20, type=int), 1), 50)

    if search_type not in ("all", "machine", "error"):
        return jsonify({"error": "Invalid type"}), 400

    result = {
        "query": query,
        "type": search_type,
        "machines": [],
        "errors": [],
        "counts": {"machines": 0, "errors": 0},
    }

    # Set to dedupe errors — when machine search returns related errors
    related_error_ids = set()
    machines_found = []
    errors_found = []

    if search_type in ("all", "machine"):
        mq = _machine_query_for_user(query, current_user)
        machines = mq.order_by(Machine.machine_code).limit(limit).all()
        machines_found = machines

        # Collect related errors from M2M linkage (legacy)
        for m in machines:
            for e in m.errors:
                related_error_ids.add(e.id)

        # Auto-pair: match machines ↔ errors via error.machine_name field
        if machines:
            # Candidate errors: those whose machine_name is non-empty
            candidate_errors = (
                Error.query
                .filter(
                    Error.status != Error.STATUS_ARCHIVED,
                    Error.machine_name.isnot(None),
                    Error.machine_name != "",
                )
                .all()
            )
            auto_pairs = _auto_pair_errors(machines, candidate_errors)
            for mid, errs in auto_pairs.items():
                for e in errs:
                    related_error_ids.add(e.id)

        # Serialize machines with related errors (M2M + auto-paired)
        result["machines"] = [
            _serialize_machine_with_related(m, related_error_ids)
            for m in machines
        ]
        result["counts"]["machines"] = len(machines)

    if search_type in ("all", "error"):
        eq = _error_query(query)
        errors = eq.order_by(Error.error_code).limit(limit).all()
        errors_found = errors
        result["counts"]["errors"] = len(errors)

    # If machine search (or all) — include related errors
    if search_type in ("all", "machine") and related_error_ids:
        # Fetch all related errors that aren't already in errors_found
        already_ids = {e.id for e in errors_found}
        extra_ids = related_error_ids - already_ids
        if extra_ids:
            extra_errors = Error.query.filter(
                Error.id.in_(extra_ids),
                Error.status != Error.STATUS_ARCHIVED,
            ).order_by(Error.error_code).limit(limit).all()
            errors_found.extend(extra_errors)

    # Serialize errors
    result["errors"] = [_serialize_error(e) for e in errors_found]
    result["counts"]["errors"] = len(errors_found)

    return jsonify(result)
