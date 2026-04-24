import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from jira_utils import build_jql_from_config


class TestBuildJqlFromConfig:

    def _write_config(self, tmp_path, content):
        path = tmp_path / "pipeline-settings.yaml"
        path.write_text(content)
        return str(path)

    def test_full_config(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels:
    - strat-creator-3.5
  quality_labels:
    - rfe-creator-autofix-rubric-pass
    - tech-reviewed
  excluded_statuses:
    - Closed
    - Resolved
    - Draft
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        assert jql.startswith("project = RHAIRFE")
        assert 'labels = "strat-creator-3.5"' in jql
        assert 'labels = "rfe-creator-autofix-rubric-pass"' in jql
        assert 'labels = "tech-reviewed"' in jql
        assert " OR " in jql
        assert 'status NOT IN ("Closed", "Resolved", "Draft")' in jql
        assert jql.endswith("ORDER BY key ASC")

    def test_clause_ordering(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels:
    - label-a
  quality_labels:
    - label-b
  excluded_statuses:
    - Closed
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        proj_pos = jql.index("project = RHAIRFE")
        req_pos = jql.index('labels = "label-a"')
        qual_pos = jql.index('labels = "label-b"')
        status_pos = jql.index("status NOT IN")
        order_pos = jql.index("ORDER BY")
        assert proj_pos < req_pos < qual_pos < status_pos < order_pos

    def test_empty_quality_labels(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: MYPROJ
  required_labels:
    - required-one
  quality_labels: []
  excluded_statuses:
    - Closed
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        assert "project = MYPROJ" in jql
        assert 'labels = "required-one"' in jql
        assert " OR " not in jql
        assert 'status NOT IN ("Closed")' in jql

    def test_empty_excluded_statuses(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: TESTPROJ
  required_labels:
    - some-label
  quality_labels:
    - quality-one
  excluded_statuses: []
  order_by: created DESC
""")
        jql = build_jql_from_config(config)
        assert "project = TESTPROJ" in jql
        assert "status NOT IN" not in jql
        assert jql.endswith("ORDER BY created DESC")

    def test_missing_fields_use_defaults(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql: {}
""")
        jql = build_jql_from_config(config)
        assert "project = RHAIRFE" in jql
        assert "ORDER BY key ASC" in jql
        assert " OR " not in jql
        assert "status NOT IN" not in jql

    def test_missing_jql_key_uses_defaults(self, tmp_path):
        config = self._write_config(tmp_path, """\
batch_size: 5
""")
        jql = build_jql_from_config(config)
        assert "project = RHAIRFE" in jql
        assert "ORDER BY key ASC" in jql

    def test_multiple_required_labels_are_anded(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels:
    - label-alpha
    - label-beta
  quality_labels: []
  excluded_statuses: []
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        assert 'labels = "label-alpha"' in jql
        assert 'labels = "label-beta"' in jql
        parts = jql.split(" AND ")
        label_parts = [p for p in parts if "label-alpha" in p or "label-beta" in p]
        assert len(label_parts) == 2

    def test_quality_labels_grouped_with_or(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels: []
  quality_labels:
    - q1
    - q2
    - q3
  excluded_statuses: []
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        assert '(labels = "q1" OR labels = "q2" OR labels = "q3")' in jql

    def test_single_quality_label(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels: []
  quality_labels:
    - single-q
  excluded_statuses: []
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        assert '(labels = "single-q")' in jql

    def test_no_order_by(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels: []
  quality_labels: []
  excluded_statuses: []
  order_by: ""
""")
        jql = build_jql_from_config(config)
        assert "ORDER BY" not in jql

    def test_exact_format_matches(self, tmp_path):
        config = self._write_config(tmp_path, """\
jql:
  project: RHAIRFE
  required_labels:
    - strat-creator-3.5
  quality_labels:
    - rfe-creator-autofix-rubric-pass
    - tech-reviewed
  excluded_statuses:
    - Closed
    - Resolved
    - Draft
  order_by: key ASC
""")
        jql = build_jql_from_config(config)
        expected = (
            'project = RHAIRFE'
            ' AND labels = "strat-creator-3.5"'
            ' AND (labels = "rfe-creator-autofix-rubric-pass"'
            ' OR labels = "tech-reviewed")'
            ' AND status NOT IN ("Closed", "Resolved", "Draft")'
            ' ORDER BY key ASC'
        )
        assert jql == expected
