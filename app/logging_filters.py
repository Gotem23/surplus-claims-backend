import logging
import re


class RedactApiKeyFilter(logging.Filter):
    """
    Redacts X-API-Key if it appears anywhere in a log message.
    This protects against accidental header dumps / debug logs.
    """

    # Covers:
    #   X-API-Key: value
    #   "X-API-Key": "value"
    #   'X-API-Key': 'value'
    _patterns = [
        re.compile(r"(X-API-Key\s*:\s*)([^\s,;]+)", re.IGNORECASE),
        re.compile(r'("X-API-Key"\s*:\s*")([^"]+)(")', re.IGNORECASE),
        re.compile(r"('X-API-Key'\s*:\s*')([^']+)(')", re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            redacted = msg
            for p in self._patterns:
                redacted = p.sub(
                    r"\1***REDACTED***\3"
                    if p.pattern.startswith(('"', "'"))
                    else r"\1***REDACTED***",
                    redacted,
                )

            # Replace record message safely
            if redacted != msg:
                record.msg = redacted
                record.args = ()
        except Exception:
            # Never block logging if filter fails
            pass
        return True
