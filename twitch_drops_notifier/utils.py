import datetime


def get_timestamp():
    return datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()


def get_datetime(timestamp: str) -> datetime.datetime:
    try:
        return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
    except:
        pass
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")
