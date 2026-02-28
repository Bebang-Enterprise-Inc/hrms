import hrms.api.billing as billing_api
import hrms.patches.v16_0.normalize_store_type_category_to_store_type as store_type_patch
from hrms.hr.doctype.bei_store_type.bei_store_type import resolve_store_type, normalize_store_type


def test_normalize_store_type_contract_aliases():
    assert normalize_store_type("jv") == "JV"
    assert normalize_store_type("Joint Venture") == "JV"
    assert normalize_store_type("managed_franchise") == "Managed Franchise"
    assert normalize_store_type("full-franchise") == "Full Franchise"


def test_resolve_store_type_prefers_canonical_then_legacy():
    assert resolve_store_type("Managed Franchise", "joint venture") == "Managed Franchise"
    assert resolve_store_type("", "joint venture stores") == "JV"
    assert resolve_store_type(None, "full franchise") == "Full Franchise"


def test_billing_store_type_reader_supports_legacy_column(monkeypatch):
    class FakeDB:
        def get_table_columns(self, table_name):
            assert table_name == "tabBEI Store Type"
            return ["name", "store", "store_type_category"]

    sample_rows = [
        {"store": "Store A", "store_type_category": "joint venture"},
        {"store": "Store B", "store_type_category": "managed_franchise"},
    ]

    monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
    monkeypatch.setattr(
        billing_api.frappe,
        "get_all",
        lambda *args, **kwargs: [dict(row) for row in sample_rows],
    )

    normalized_rows = billing_api._get_store_type_records()

    assert normalized_rows[0]["store_type"] == "JV"
    assert normalized_rows[1]["store_type"] == "Managed Franchise"


def test_store_type_patch_is_idempotent_and_schema_safe(monkeypatch):
    class FakePatchDB:
        def __init__(self):
            self.columns = {
                "tabBEI Store Type": ["name", "store", "store_type_category"],
                "tabBEI Billing Schedule": ["name", "store_type"],
            }
            self.rows = {
                "tabBEI Store Type": [
                    {"name": "ST-001", "store": "Store A", "store_type_category": "joint venture"},
                ],
                "tabBEI Billing Schedule": [
                    {"name": "BILL-001", "store_type": "managed-franchise"},
                ],
            }
            self.commit_calls = 0

        def table_exists(self, table_name):
            return table_name in self.columns

        def get_table_columns(self, table_name):
            return list(self.columns.get(table_name, []))

        def sql(self, query, as_dict=False):
            table_name = query.split("FROM `", 1)[1].split("`", 1)[0]
            data = self.rows.get(table_name, [])
            if as_dict:
                return [dict(row) for row in data]
            return data

        def set_value(self, doctype, docname, fieldname, value, update_modified=False):
            table_name = f"tab{doctype}"
            for row in self.rows.get(table_name, []):
                if row["name"] == docname:
                    row[fieldname] = value
                    break

        def commit(self):
            self.commit_calls += 1

    fake_db = FakePatchDB()
    monkeypatch.setattr(store_type_patch.frappe, "db", fake_db)

    first_updates = store_type_patch.execute()
    second_updates = store_type_patch.execute()

    assert first_updates == 2
    assert second_updates == 0
    assert fake_db.commit_calls == 1

    assert fake_db.rows["tabBEI Store Type"][0]["store_type_category"] == "JV"
    assert fake_db.rows["tabBEI Billing Schedule"][0]["store_type"] == "Managed Franchise"
