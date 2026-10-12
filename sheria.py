"""sheria.py — Public API for the harmony rule system.

Wire every pass module together and expose the same public names as
before: KeySignature, RomanNumeralAnalyzer, RulesEngine, SubmissionEngine.
"""

from sheria_base import (
    KeySignature,
    RomanNumeralAnalyzer,
    HarmonyRule,
    ErrorDetail,
    GradingReport,
    RulesEngine as _BaseRulesEngine,
    SubmissionEngine,
    register_handlers,
    list_handlers,
)

# Import each pass module for its side effect of registering handlers.
import sheria_pass1  # noqa: F401   (Units 1-5)
import sheria_pass2  # noqa: F401   (Units 6-10)
import sheria_pass3  # noqa: F401   (Units 11-15)
import sheria_pass4  # noqa: F401   (Units 16-21)
import sheria_pass5  # noqa: F401   (Units 22-26)
import sheria_pass6  # noqa: F401   (Units 27-32)


RULESETS = [
    "rules_pass1.json",
    "rules_pass2.json",
    "rules_pass3.json",
    "rules_pass4.json",
    "rules_pass5.json",
    "rules_pass6.json",
]

# The quality analyzer auto-discovers every quality_passN.json file
# in the same directory. This list is documentation only — it names
# the passes that are expected to exist. If a file is missing from
# the directory, the analyzer will simply load fewer rules.
QUALITY_SETS = [
    "quality_pass1.json",
    "quality_pass2.json",
    "quality_pass3.json",
    "quality_pass4.json",
    "quality_pass5.json",
    "quality_pass6.json",
    "quality_pass7.json",
]


class RulesEngine(_BaseRulesEngine):
    def __init__(self, json_paths=None):
        super().__init__(json_paths or RULESETS)


__all__ = [
    "KeySignature",
    "RomanNumeralAnalyzer",
    "HarmonyRule",
    "ErrorDetail",
    "GradingReport",
    "RulesEngine",
    "SubmissionEngine",
    "register_handlers",
    "list_handlers",
    "RULESETS",
    "QUALITY_SETS",
]