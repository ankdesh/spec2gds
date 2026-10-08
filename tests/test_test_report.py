"""Check that HTML reports retain real outcomes and exclude implementation data."""

from html.parser import HTMLParser

from scripts import test_profiles as runner
from scripts.test_report import render_report


class ReportContent(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_data(self, data):
        self.text.append(data)


def report_content(html):
    parser = ReportContent()
    parser.feed(html)
    return parser


def test_report_explains_failed_live_check_and_omits_raw_metadata(tmp_path):
    path = tmp_path / "live-wire-range"
    path.mkdir()
    (path / "command.log").write_text("ExpectError: Timeout 90000ms exceeded while waiting on the predicate")
    report = {"profile": "fast", "status": "failed", "schema_version": "private-schema",
              "source_revision": "private-source-hash", "versions": {"node": "private-version"},
              "suites": [
                  {"id": "build-assistant", "status": "passed", "duration_seconds": 12},
                  {"id": "live-wire-range", "status": "failed", "duration_seconds": 90,
                   "command": ["private-command"], "output": "private-output-path"},
              ]}
    html = render_report(report, tmp_path)
    parsed = report_content(html)
    text = " ".join(parsed.text)
    assert parsed.tags.count("table") == 2
    assert "Live model: change a wire range" in text
    assert "Timed out after 1 min 30 sec" in text
    assert "Build AI Assistant" in text
    assert "1 min 42 sec" in text
    for hidden in ("private-schema", "private-source-hash", "private-version", "private-command",
                   "private-output-path", "ExpectError", "live-wire-range"):
        assert hidden not in html


def test_incomplete_results_are_not_presented_as_passed(tmp_path):
    report = {"profile": "fast", "status": "incomplete", "suites": [
        {"id": "live-description", "status": "unverified",
         "reason": "OPENAI_API_KEY is unavailable; no live inference was performed."},
        {"id": "hardware-extensive", "status": "unverified",
         "reason": "Required hardware tool verilator is unavailable."},
    ]}
    html = render_report(report, tmp_path)
    assert "Live model access is not configured." in html
    assert "Verilator 5.x is required" in html
    assert "This run is incomplete." in html
    assert 'class="status passed"' not in html
    assert "OPENAI_API_KEY" not in html


def test_report_escapes_untrusted_text_without_executable_content(tmp_path):
    html = render_report({"profile": "fast", "status": "failed", "suites": [
        {"id": '<img src=x onerror="alert(1)">', "status": "failed"},
    ], "coverage_gaps": ["<script>alert(2)</script>"]}, tmp_path)
    parsed = report_content(html)
    assert "script" not in parsed.tags
    assert "img" not in parsed.tags
    assert "&lt;" in html


def test_running_and_skipped_checks_keep_their_limits_visible(tmp_path):
    html = render_report({"profile": "integration", "status": "running", "suites": [
        {"id": "activity-api", "status": "passed", "duration_seconds": 2,
         "skipped": [{"message": "Optional tool absent"}]},
    ]}, tmp_path)
    assert "In progress" in html
    assert "1 optional check did not run" in html
    assert "outside this result" in html


def test_report_writer_redacts_secrets_and_generates_both_formats(tmp_path):
    report = {"profile": "fast", "status": "passed", "suites": [],
              "coverage_gaps": ["private-report-key"]}
    runner.write_reports(report, tmp_path, {"OPENAI_API_KEY": "private-report-key"})
    for filename in ("summary.html", "summary.json"):
        contents = (tmp_path / filename).read_text()
        assert "private-report-key" not in contents
        assert "[REDACTED]" in contents
