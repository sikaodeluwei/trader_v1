from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCANNER = (
    PROJECT_ROOT
    / "tools"
    / "validation"
    / "ninjatrader"
    / "ScanMnq5mSourceInventory.cs"
)


def _scanner_source() -> str:
    assert SCANNER.is_file(), f"missing scanner source: {SCANNER}"
    return SCANNER.read_text(encoding="utf-8")


def _code_without_comments(source: str) -> str:
    return re.sub(r"//[^\r\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _prohibited_surface_findings(source: str) -> set[str]:
    code = _code_without_comments(source)
    findings: set[str] = set()
    checks = {
        "artifact-write-api": r"\b(?:File|Directory)\.(?:WriteAll(?:Text|Bytes|Lines)|OpenWrite|Create|Copy|Move|CreateDirectory)\s*\(",
        "stream-writer": r"\bnew\s+(?:FileStream|StreamWriter|BinaryWriter)\b",
        "serializer-stream-output": r"\b(?:JavaScriptSerializer|JsonSerializer|XmlSerializer)\b[\s\S]{0,160}?\.Serialize\s*\(\s*(?:new\s+(?:FileStream|StreamWriter)|[A-Za-z_]\w*(?:stream|writer))\b",
        "raw-ohlcv": r"\b(?:Time|Open|High|Low|Close|Volume)\s*\[",
        "integration": r"\b(?:hierarchy|oracle|project|comparator)\b|\b(?:Run|Execute|Invoke)(?:Hierarchy|Oracle|Project|Comparator)\b",
        "policy-or-selection": r"\b(?:eligible|exclusion_reasons|selection|selector|strata)\b|\b(?:Math\.)?Floor\s*\([^\r\n]*\*[^\r\n]*/\s*10(?:\.0)?\b",
        "structural-summary": r"\b(?:min(?:imum)?Price|max(?:imum)?Price|(?:price|session|bar)Range(?:Summary|Value)?|(?:simple|log)Return(?:Summary|Value)|Volatility(?:Summary|Value)?|Swing(?:Count|Summary))\b|\bMath\.(?:Min|Max)\s*\(\s*(?:Open|High|Low|Close)\s*\[",
    }
    for name, pattern in checks.items():
        if re.search(pattern, code, flags=re.IGNORECASE):
            findings.add(name)
    return findings


def test_scanner_declares_the_frozen_ninjatrader_contract() -> None:
    """Catches a scanner shell that drifts from the approved MNQ identity."""
    source = _scanner_source()

    assert "namespace NinjaTrader.NinjaScript.Indicators" in source
    assert re.search(
        r"public\s+class\s+ScanMnq5mSourceInventory\s*:\s*Indicator\b",
        source,
    )
    for constant in (
        'private const string ApprovedContractLabel = "MNQ SEP26";',
        "private const int ApprovedExpiryMonth = 9;",
        "private const int ApprovedExpiryYear = 2026;",
        'private const string ApprovedRangeStart = "2026-06-22";',
        'private const string ApprovedRangeEnd = "2026-07-24";',
        "private const BarsPeriodType ApprovedBarsPeriodType = BarsPeriodType.Minute;",
        "private const int ApprovedBarsPeriodValue = 5;",
        'private const string ApprovedTradingHoursName = "CME US Index Futures ETH";',
        'private const string ScanFileName = "inventory_scan.json";',
        'private const string RuntimeFileName = "inventory_runtime_capture.json";',
        'private const string TradingHoursFileName = "trading_hours_template.xml";',
        'private const string ConfigFileName = "NinjaTrader.Config.xml";',
        '"NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1";',
    ):
        assert constant in source

    assert "BarsPeriod.BarsPeriodType != ApprovedBarsPeriodType" in source
    assert "BarsPeriod.Value != ApprovedBarsPeriodValue" in source
    assert re.search(r"\bInstrument\.FullName\s*(?:==|!=)", source) is None
    assert "Calculate = Calculate.OnBarClose;" in source
    assert "State == State.SetDefaults" in source


def test_scanner_keeps_the_neutral_lifecycle_and_session_contract() -> None:
    """Catches removal of lifecycle evidence or exchange-date session authority."""
    source = _scanner_source()

    for marker in (
        "inventory scanner initialized event_time=",
        "inventory realtime lifecycle observed event_time=",
        "inventory scan armed event_time=",
        "inventory scan complete event_time=",
    ):
        assert marker in source

    assert "new SessionIterator(Bars)" in source
    assert "nameof(SessionIterator.ActualTradingDayExchange)" in source
    assert "ActualTradingDayExchange.Date" not in source
    assert ".DayOfWeek" not in source


def test_scanner_does_not_preempt_task_three_with_outputs_or_policy() -> None:
    """Catches scanner code that writes artifacts or makes eligibility decisions."""
    source = _scanner_source()
    assert "bars.txt" not in _code_without_comments(source)
    assert _prohibited_surface_findings(source) == set()


@pytest.mark.parametrize(
    ("source", "expected_finding"),
    (
        ("File.OpenWrite(path);", "artifact-write-api"),
        ("File.WriteAllLines(path, rows);", "artifact-write-api"),
        ("using (var stream = new FileStream(path, FileMode.Create)) { }", "stream-writer"),
        ("using (var writer = new StreamWriter(path)) { }", "stream-writer"),
        (
            "new JavaScriptSerializer().Serialize(outputStream, payload);",
            "serializer-stream-output",
        ),
        (
            'string row = string.Join(";", Time[0], Open[0], High[0], Low[0], Close[0], Volume[0]);',
            "raw-ohlcv",
        ),
        ("RunOracle();", "integration"),
        ("int start = (int)Math.Floor(index * dates.Count / 10.0);", "policy-or-selection"),
        ("double minPrice = Low[0];", "structural-summary"),
        ("double maxPrice = High[0];", "structural-summary"),
        ("double priceRange = highest - lowest;", "structural-summary"),
        ("double simpleReturnSummary = closeValue - openValue;", "structural-summary"),
        ("double volatilityValue = variance;", "structural-summary"),
        ("int swingCount = 0;", "structural-summary"),
    ),
)
def test_prohibited_surface_checks_reject_realistic_mutations(
    source: str,
    expected_finding: str,
) -> None:
    """Catches newly introduced Task 3 output, policy, and selection code."""
    assert expected_finding in _prohibited_surface_findings(source)


def test_prohibited_surface_checks_ignore_comments_and_partial_words() -> None:
    """Keeps word-boundary checks from rejecting comments or benign identifiers."""
    assert _prohibited_surface_findings(
        "// RunOracle(); hierarchy comparator\nstring projected = \"projected\";"
    ) == set()


def test_property_annotations_must_be_contiguous_with_their_declarations() -> None:
    """Catches a later property borrowing a preceding NinjaScript attribute."""
    source = _scanner_source()
    for property_name, display_name in (
        ("AcquisitionId", "Acquisition ID"),
        ("CohortId", "Cohort ID"),
        ("ArmFilePath", "Operator arm file"),
        ("OutputDirectoryPath", "Output directory"),
    ):
        declaration = rf"public string {property_name} {{ get; set; }}"
        pattern = rf"\[NinjaScriptProperty\]\s*\[Display\([^\]]*\)\]\s*{re.escape(declaration)}"
        assert re.search(pattern, source)
        mutated = source.replace(
            "[NinjaScriptProperty]\n"
            + f'        [Display(Name = "{display_name}",',
            f'[Display(Name = "{display_name}",',
            1,
        )
        assert re.search(pattern, mutated) is None
