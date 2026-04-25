"""Integration tests for jira_utils search/filter functions against jira-emulator."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from jira_utils import search_issues, find_processed_rfe_ids, _extract_rfe_keys_from_issues


class TestSearchIssues:

    def test_returns_all_matching_issues(self, jira):
        jira.create("RHAIRFE-500", "Feature A", "Description A")
        jira.create("RHAIRFE-501", "Feature B", "Description B")
        jira.create("RHAIRFE-502", "Feature C", "Description C")

        issues = search_issues(
            jira.url, "admin", "admin",
            'project = RHAIRFE',
        )
        keys = {i["key"] for i in issues}
        assert "RHAIRFE-500" in keys
        assert "RHAIRFE-501" in keys
        assert "RHAIRFE-502" in keys

    def test_returns_requested_fields(self, jira):
        jira.create("RHAIRFE-510", "Searchable feature",
                     "Some description", labels=["alpha", "beta"])

        issues = search_issues(
            jira.url, "admin", "admin",
            'project = RHAIRFE AND key = RHAIRFE-510',
            fields=["summary", "labels"],
        )
        assert len(issues) == 1
        fields = issues[0]["fields"]
        assert fields["summary"] == "Searchable feature"
        assert "alpha" in fields["labels"]
        assert "beta" in fields["labels"]

    def test_jql_label_filter(self, jira):
        jira.create("RHAIRFE-520", "Labeled", "Desc",
                     labels=["target-label"])
        jira.create("RHAIRFE-521", "Unlabeled", "Desc")

        issues = search_issues(
            jira.url, "admin", "admin",
            'project = RHAIRFE AND labels = "target-label"',
            fields=["key", "labels"],
        )
        keys = {i["key"] for i in issues}
        assert "RHAIRFE-520" in keys
        assert "RHAIRFE-521" not in keys

    def test_empty_result_set(self, jira):
        issues = search_issues(
            jira.url, "admin", "admin",
            'project = NONEXISTENT',
        )
        assert issues == []

    def test_pagination_collects_all_results(self, jira):
        for i in range(530, 536):
            jira.create(f"RHAIRFE-{i}", f"Feature {i}", f"Desc {i}")

        issues = search_issues(
            jira.url, "admin", "admin",
            'project = RHAIRFE AND key >= RHAIRFE-530 AND key <= RHAIRFE-535',
            max_results=2,
        )
        keys = {i["key"] for i in issues}
        assert len(keys) == 6
        for i in range(530, 536):
            assert f"RHAIRFE-{i}" in keys

    def test_returns_issuelinks_field(self, jira):
        jira.create("RHAIRFE-540", "Source", "Src desc")
        jira.create("RHAISTRAT-540", "Clone", "Clone desc")
        jira.request("POST", "/rest/api/3/issueLink", {
            "type": {"name": "Cloners"},
            "inwardIssue": {"key": "RHAISTRAT-540"},
            "outwardIssue": {"key": "RHAIRFE-540"},
        })

        issues = search_issues(
            jira.url, "admin", "admin",
            'key = RHAISTRAT-540',
            fields=["issuelinks"],
        )
        assert len(issues) == 1
        links = issues[0]["fields"]["issuelinks"]
        assert len(links) >= 1
        link_type_names = {lk["type"]["name"] for lk in links}
        assert "Cloners" in link_type_names


class TestExtractRfeKeysFromIssues:

    def test_extracts_outward_rhairfe_keys(self):
        issues = [
            {
                "key": "RHAISTRAT-100",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "RHAIRFE-10"},
                        },
                    ],
                },
            },
            {
                "key": "RHAISTRAT-200",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "RHAIRFE-20"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == {"RHAIRFE-10", "RHAIRFE-20"}

    def test_extracts_inward_rhairfe_keys(self):
        issues = [
            {
                "key": "RHAISTRAT-300",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "inwardIssue": {"key": "RHAIRFE-30"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == {"RHAIRFE-30"}

    def test_ignores_non_cloners_link_type(self):
        issues = [
            {
                "key": "RHAISTRAT-400",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Related"},
                            "outwardIssue": {"key": "RHAIRFE-40"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == set()

    def test_ignores_non_rhairfe_keys(self):
        issues = [
            {
                "key": "RHAISTRAT-500",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "OTHER-50"},
                        },
                        {
                            "type": {"name": "Cloners"},
                            "inwardIssue": {"key": "FOOBAR-60"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == set()

    def test_mixed_links(self):
        issues = [
            {
                "key": "RHAISTRAT-600",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "RHAIRFE-60"},
                        },
                        {
                            "type": {"name": "Related"},
                            "outwardIssue": {"key": "RHAIRFE-99"},
                        },
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "OTHER-70"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == {"RHAIRFE-60"}

    def test_empty_issues_list(self):
        result = _extract_rfe_keys_from_issues([])
        assert result == set()

    def test_issue_with_no_links(self):
        issues = [
            {
                "key": "RHAISTRAT-700",
                "fields": {
                    "issuelinks": [],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == set()

    def test_missing_issuelinks_field(self):
        issues = [
            {
                "key": "RHAISTRAT-800",
                "fields": {},
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == set()

    def test_deduplicates_keys(self):
        issues = [
            {
                "key": "RHAISTRAT-901",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "RHAIRFE-90"},
                        },
                    ],
                },
            },
            {
                "key": "RHAISTRAT-902",
                "fields": {
                    "issuelinks": [
                        {
                            "type": {"name": "Cloners"},
                            "outwardIssue": {"key": "RHAIRFE-90"},
                        },
                    ],
                },
            },
        ]
        result = _extract_rfe_keys_from_issues(issues)
        assert result == {"RHAIRFE-90"}


class TestFindProcessedRfeIds:

    def _setup_linked_pair(self, jira, rfe_key, strat_key, labels=None):
        """Create an RFE and RHAISTRAT issue, link them with Cloners, add labels."""
        jira.create(rfe_key, f"RFE {rfe_key}", f"Description for {rfe_key}")
        jira.create(strat_key, f"Strategy for {rfe_key}",
                     f"Strategy description for {strat_key}")
        jira.request("POST", "/rest/api/3/issueLink", {
            "type": {"name": "Cloners"},
            "inwardIssue": {"key": strat_key},
            "outwardIssue": {"key": rfe_key},
        })
        if labels:
            for label in labels:
                jira.request("PUT", f"/rest/api/3/issue/{strat_key}", {
                    "update": {"labels": [{"add": label}]}
                })

    def test_returns_rfe_ids_with_skip_labels(self, jira):
        self._setup_linked_pair(jira, "RHAIRFE-100", "RHAISTRAT-500",
                                labels=["strat-creator-rubric-pass"])
        self._setup_linked_pair(jira, "RHAIRFE-200", "RHAISTRAT-600",
                                labels=["strat-creator-needs-attention"])
        self._setup_linked_pair(jira, "RHAIRFE-300", "RHAISTRAT-700")

        processed = find_processed_rfe_ids(
            jira.url, "admin", "admin",
            skip_labels=["strat-creator-rubric-pass",
                         "strat-creator-needs-attention"],
        )

        assert "RHAIRFE-100" in processed
        assert "RHAIRFE-200" in processed
        assert "RHAIRFE-300" not in processed

    def test_returns_empty_when_no_skip_labels_match(self, jira):
        self._setup_linked_pair(jira, "RHAIRFE-400", "RHAISTRAT-800")

        processed = find_processed_rfe_ids(
            jira.url, "admin", "admin",
            skip_labels=["nonexistent-label"],
        )
        assert processed == set()

    def test_empty_skip_labels(self, jira):
        self._setup_linked_pair(jira, "RHAIRFE-450", "RHAISTRAT-850",
                                labels=["some-label"])

        processed = find_processed_rfe_ids(
            jira.url, "admin", "admin",
            skip_labels=[],
        )
        assert processed == set()

    def test_single_skip_label(self, jira):
        self._setup_linked_pair(jira, "RHAIRFE-460", "RHAISTRAT-860",
                                labels=["strat-creator-rubric-pass"])
        self._setup_linked_pair(jira, "RHAIRFE-470", "RHAISTRAT-870",
                                labels=["strat-creator-needs-attention"])

        processed = find_processed_rfe_ids(
            jira.url, "admin", "admin",
            skip_labels=["strat-creator-rubric-pass"],
        )
        assert "RHAIRFE-460" in processed
        assert "RHAIRFE-470" not in processed

    def test_strat_with_multiple_labels_matched_once(self, jira):
        self._setup_linked_pair(jira, "RHAIRFE-480", "RHAISTRAT-880",
                                labels=["strat-creator-rubric-pass",
                                        "strat-creator-needs-attention"])

        processed = find_processed_rfe_ids(
            jira.url, "admin", "admin",
            skip_labels=["strat-creator-rubric-pass",
                         "strat-creator-needs-attention"],
        )
        assert "RHAIRFE-480" in processed
