from datetime import timezone


def to_local(dt):
    """Đổi datetime UTC (naive) trong CSDL sang giờ địa phương của máy chủ."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone()


def fmt_time(dt):
    return to_local(dt).strftime("%H:%M:%S") if dt else ""


def fmt_datetime(dt):
    return to_local(dt).strftime("%H:%M:%S %d/%m/%Y") if dt else ""


def fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else ""


def register_filters(app):
    app.jinja_env.filters["hms"] = fmt_time
    app.jinja_env.filters["dt"] = fmt_datetime
    app.jinja_env.filters["vndate"] = fmt_date
