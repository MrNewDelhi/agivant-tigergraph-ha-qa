"""Messy / edge-case / larger-data tests (MD1-MD12).

Deliberately tricky inputs: unicode, injection-shaped strings, extreme numerics,
duplicate primary ids, empty/whitespace values, long strings, and a 5k bulk insert.
"""
import json

import pytest

pytestmark = pytest.mark.messy


class TestMessyStrings:
    def test_MD01_unicode_emoji_round_trip(self, api, scratch_persons):
        scratch_persons.append("msg_uni")
        name = "José García 日本語 Ω 😀"
        api.upsert_person("msg_uni", name)
        assert api.get_person_name("msg_uni") == name

    def test_MD02_special_chars_no_injection(self, api, scratch_persons):
        scratch_persons.append("msg_spec")
        name = "O'Brien, \"Bob\" <script> & Co."
        api.upsert_person("msg_spec", name)
        assert api.get_person_name("msg_spec") == name

    def test_MD08_empty_string_value(self, api, scratch_persons):
        scratch_persons.append("msg_empty")
        api.upsert_person("msg_empty", "")
        assert api.get_person_name("msg_empty") == ""

    def test_MD09_whitespace_only_preserved(self, api, scratch_persons):
        scratch_persons.append("msg_ws")
        api.upsert_person("msg_ws", "   ")
        assert api.get_person_name("msg_ws") == "   "

    def test_MD10_long_string_500_chars(self, api, scratch_persons):
        scratch_persons.append("msg_long")
        name = "X" * 500
        api.upsert_person("msg_long", name)
        assert api.get_person_name("msg_long") == name


class TestMessyNumerics:
    def test_MD03_very_large_balance(self, api, scratch_accounts):
        scratch_accounts.append("msg_big")
        api.upsert_account("msg_big", 999999999999.99)
        assert api.get_account("msg_big")["balance"] == 999999999999.99

    def test_MD04_negative_balance(self, api, scratch_accounts):
        scratch_accounts.append("msg_neg")
        api.upsert_account("msg_neg", -500.25)
        assert api.get_account("msg_neg")["balance"] == -500.25

    def test_MD05_zero_balance(self, api, scratch_accounts):
        scratch_accounts.append("msg_zero")
        api.upsert_account("msg_zero", 0.0)
        assert api.get_account("msg_zero")["balance"] == 0

    def test_MD06_very_small_balance(self, api, scratch_accounts):
        scratch_accounts.append("msg_tiny")
        api.upsert_account("msg_tiny", 0.00000001)
        assert api.get_account("msg_tiny")["balance"] == 0.00000001

    def test_MD07_duplicate_primary_id_dedups_last_wins(self, api, scratch_accounts):
        scratch_accounts.append("msg_dup")
        api.upsert_account("msg_dup", 100.0)
        api.upsert_account("msg_dup", 200.0)
        assert api.get_account("msg_dup")["balance"] == 200.0


class TestLargerData:
    BATCH, TOTAL = 1000, 5000

    def test_MD11_bulk_insert_5000_vertices(self, api):
        for start in range(0, self.TOTAL, self.BATCH):
            verts = {f"bulk{i}": {"balance": {"value": float(i)}}
                     for i in range(start, start + self.BATCH)}
            api.s.post(api.graph, timeout=30,
                       data=json.dumps({"vertices": {"Account": verts}}))
        sample = (0, 1234, 2500, 4999)
        present = sum(1 for i in sample if api.get_account(f"bulk{i}") is not None)
        assert present == len(sample)

    def test_MD12_bulk_value_integrity(self, api):
        assert api.get_account("bulk4999")["balance"] == 4999
