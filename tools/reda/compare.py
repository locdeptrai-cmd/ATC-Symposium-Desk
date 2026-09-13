from __future__ import annotations

from .concept import AtcConcept, CompareIssue, IssueType, PhraseologyRule, Severity
from .normalize_fn import COMPARE_FNS, compare_callsign, is_ack_only

CRITICAL_RED = {"level", "squawk", "runway"}
CRITICAL_AMBER = {"heading", "speed", "freq", "qnh"}

PARAM_FIELDS = ("level", "heading", "speed", "squawk", "freq", "qnh", "runway")


def _get_param(concept: AtcConcept, field: str):
    if field == "callsign":
        return concept.callsign_norm
    return getattr(concept.params, field, None)


def _fmt(value) -> str | None:
    if value is None:
        return None
    return str(value)


def _severity_for(field: str, rule: PhraseologyRule | None) -> Severity:
    if rule:
        return rule.severity
    if field in CRITICAL_RED:
        return Severity.RED
    if field in CRITICAL_AMBER:
        return Severity.AMBER
    return Severity.AMBER


def _rule_for(rules: list[PhraseologyRule], field: str, intent: str | None) -> PhraseologyRule | None:
    for rule in rules:
        if rule.field == field and (rule.intent in (None, "*", intent) or rule.intent == intent):
            return rule
    for rule in rules:
        if rule.field == field:
            return rule
    return None


def fields_for(atco: AtcConcept) -> list[str]:
    present = []
    for field in PARAM_FIELDS:
        if _get_param(atco, field) is not None:
            present.append(field)
    return present


def missing_readback(atco: AtcConcept, rule: PhraseologyRule | None = None) -> CompareIssue:
    field = fields_for(atco)[0] if fields_for(atco) else "*"
    r = rule
    return CompareIssue(
        type=IssueType.MISSING_READBACK,
        field=field,
        expected=_fmt(_get_param(atco, field)) if field != "*" else atco.raw_text,
        got=None,
        severity=Severity.RED if field in CRITICAL_RED or field == "*" else Severity.AMBER,
        rule_id=r.rule_id if r else "R_LEVEL_MUST",
        explanation_vi=(
            f"Không có readback trong cửa sổ ghép cặp. Huấn lệnh {atco.intent.value} "
            f"bắt buộc readback (Doc 4444 / Annex 11 3.7.3.1)."
        ),
        explanation_en="Mandatory readback missing within pairing window.",
    )


def compare(
    atco: AtcConcept,
    pilot: AtcConcept | None,
    rules: list[PhraseologyRule],
) -> list[CompareIssue]:
    if atco.must_readback and pilot is None:
        rb_rule = next((r for r in rules if r.rule_id.endswith("_MUST")), None)
        return [missing_readback(atco, rb_rule)]

    assert pilot is not None
    issues: list[CompareIssue] = []

    cs_rule = _rule_for(rules, "callsign", "*")
    if atco.callsign_norm and pilot.callsign_norm and not compare_callsign(atco.callsign_norm, pilot.callsign_norm):
        issues.append(
            CompareIssue(
                type=IssueType.CALLSIGN_ERROR,
                field="callsign",
                expected=atco.callsign_norm,
                got=pilot.callsign_norm,
                severity=Severity.RED,
                rule_id=cs_rule.rule_id if cs_rule else "R_CALLSIGN_CLOSE",
                explanation_vi="Readback phải kết thúc / chứa đúng callsign tàu bay.",
                explanation_en="Readback should include the correct aircraft call sign.",
            )
        )

    for field in fields_for(atco):
        rule = _rule_for(rules, field, atco.intent.value)
        a = _get_param(atco, field)
        p = _get_param(pilot, field)
        fn_name = rule.compare_fn if rule else "exact_norm"
        fn = COMPARE_FNS.get(fn_name, COMPARE_FNS["exact_norm"])
        sev = _severity_for(field, rule)
        rule_id = rule.rule_id if rule else f"R_{field.upper()}_MUST"
        desc_vi = rule.description_vi if rule else f"Trường {field} phải được readback đúng."
        desc_en = rule.description_en if rule else f"{field} shall be read back."
        clause = f"{rule.source_doc} {rule.source_clause or ''}".strip() if rule else "DOC4444"

        if a is not None and p is None:
            issues.append(
                CompareIssue(
                    type=IssueType.OMISSION,
                    field=field,
                    expected=_fmt(a),
                    got=None,
                    severity=sev,
                    rule_id=rule_id,
                    explanation_vi=f"{desc_vi} Thiếu {field}: kỳ vọng {_fmt(a)}. ({clause})",
                    explanation_en=f"{desc_en} Omitted {field}: expected {_fmt(a)}.",
                )
            )
        elif a is not None and not fn(a, p):
            issues.append(
                CompareIssue(
                    type=IssueType.MISMATCH,
                    field=field,
                    expected=_fmt(a),
                    got=_fmt(p),
                    severity=sev,
                    rule_id=rule_id,
                    explanation_vi=(
                        f"{desc_vi} {field}: kỳ vọng {_fmt(a)}, readback {_fmt(p)}. ({clause})"
                    ),
                    explanation_en=f"{desc_en} {field}: expected {_fmt(a)}, got {_fmt(p)}.",
                )
            )

    roger_rule = next((r for r in rules if r.rule_id == "R_ROGER_NOT_RB"), None)
    if is_ack_only(pilot.raw_text) and atco.must_readback:
        issues.append(
            CompareIssue(
                type=IssueType.NON_STANDARD,
                field="*",
                expected=_fmt(_get_param(atco, fields_for(atco)[0])) if fields_for(atco) else atco.raw_text,
                got=pilot.raw_text,
                severity=Severity.AMBER,
                rule_id=roger_rule.rule_id if roger_rule else "R_ROGER_NOT_RB",
                explanation_vi=(
                    "Roger/Wilco không thay thế readback số liệu an toàn "
                    "(Doc 4444 §4.5.7.5)."
                ),
                explanation_en="Roger/Wilco is not an acceptable substitute for safety-item readback.",
            )
        )

    if not issues:
        return [
            CompareIssue(
                type=IssueType.OK,
                field=None,
                expected=None,
                got=None,
                severity=Severity.GREEN,
                rule_id="OK",
                explanation_vi="Readback khớp concept.",
                explanation_en="Concept-level readback matches.",
            )
        ]
    return issues
