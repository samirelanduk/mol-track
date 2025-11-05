import csv
import tempfile
import pytest
from app.utils import enums
from app import models
from tests.conftest import BLACK_DIR, read_json, _preload_compounds
from tests.utils.test_base_registrar import BaseRegistrarTest
from tests.utils.test_mixins import CRUDTestsMixin, SynonymTestsMixin


def extract_name_entity_type(items):
    return sorted(
        [{"name": item["name"], "entity_type": item["entity_type"].upper()} for item in items], key=lambda x: x["name"]
    )


def assert_name_entity_type_equal(actual, expected):
    actual_name_entity_type = extract_name_entity_type(actual)
    expected_name_entity_type = extract_name_entity_type(expected)
    assert actual_name_entity_type == expected_name_entity_type


@pytest.fixture
def first_compound_with_synonyms(client, preload_schema, preload_compounds, api_headers):
    response = client.get("/v1/compounds/", headers=api_headers)
    assert response.status_code == 200
    compounds = response.json()
    assert compounds, "No compounds returned"

    first = compounds[0]
    synonyms = [p for p in first["properties"] if p["semantic_type_id"] == 1]
    assert synonyms, f"No synonym properties found for compound {first['canonical_smiles']}"

    return first, synonyms


@pytest.mark.parametrize(
    "endpoint,schema_file,response_key,expected_keys",
    [
        ("/v1/schema/compounds", "compounds_schema.json", None, ["properties", "synonym_types"]),
        ("/v1/schema/compounds/synonyms", "compounds_schema.json", None, ["synonym_types"]),
        ("/v1/schema/batches", "batches_schema.json", "properties", ["properties", "synonym_types"]),
        ("/v1/schema/batches/synonyms", "batches_schema.json", "synonym_types", ["synonym_types"]),
    ],
)
def test_schema(client, endpoint, schema_file, response_key, expected_keys, preload_schema, api_headers):
    response = client.get(endpoint, headers=api_headers)
    assert response.status_code == 200

    response_data = response.json()
    actual = response_data if response_key is None else response_data[response_key]
    expected_data = read_json(BLACK_DIR / schema_file)
    expected = []
    for key in expected_keys:
        expected.extend(expected_data.get(key, []))

    if "/compounds" in endpoint:
        expected.append({"name": "corporate_compound_id", "entity_type": enums.EntityType.COMPOUND})
    if "/batches" in endpoint:
        expected.append({"name": "corporate_batch_id", "entity_type": enums.EntityType.BATCH})

    assert_name_entity_type_equal(actual, expected)

    if "/v1/schema/batches" in endpoint:
        assert "additions" in response_data


class TestCompoundsRegistrar(BaseRegistrarTest, SynonymTestsMixin, CRUDTestsMixin):
    entity_name = "compounds"
    expected_properties = {
        "EPA Compound ID",
        "corporate_compound_id",
        "MolLogP",
        "Source Compound Code",
        "CAS",
        "Source",
        "Common Name",
    }
    expected_first = {
        "Common Name": "1,3-Benzenedicarboxylic acid",
        "CAS": "121-91-5",
        "EPA Compound ID": "EPA-001",
        "MolLogP": 1.082999945,
        "Source": "EPA",
        "Source Compound Code": "EPA-001",
    }
    preload_func = staticmethod(_preload_compounds)
    get_response_model = models.CompoundResponse
    first_entity_fixture_name = "first_compound_with_synonyms"

    def test_register_source_not_in_vocabulary(self, client, api_headers, preload_schema):
        allowed_sources = ["ACME", "E-Molecule", "EPA", "Enamine", "Pharmaron", "Sigma-Aldrich", "WuXi"]
        test_source = "TestSource"

        with tempfile.NamedTemporaryFile(mode="w+", newline="", suffix=".csv", delete=False) as tmp_file:
            writer = csv.DictWriter(tmp_file, fieldnames=["smiles", "Source"])
            writer.writeheader()
            writer.writerow({"smiles": "CCO", "Source": test_source})
            tmp_file_path = tmp_file.name

        response = _preload_compounds(client=client, csv_path=tmp_file_path, api_headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        print("datass")
        print(data)
        assert data[0]["registration_status"] == "failed"
        expected_error = f"Value '{test_source}' is not in the allowed choices: {allowed_sources}"
        assert data[0]["registration_error_message"] == expected_error

    def test_update_allowed_values_in_vocabulary(self, client, api_headers, preload_schema):
        allowed_sources = ["ACME", "E-Molecule", "EPA", "Enamine", "Pharmaron", "Sigma-Aldrich", "WuXi"]
        new_sources = ["TestSource1", "TestSource2"]
        updated_sources = allowed_sources + new_sources

        schema = client.get("/v1/schema/", headers=api_headers)
        assert schema.status_code == 200
        schema_json = schema.json()

        source_property = next((prop for prop in schema_json if prop.get("name") == "Source"), None)
        assert source_property is not None

        payload = {"property_id": source_property["id"], "allowed_values": updated_sources}

        response = client.post("/v1/schema/vocabulary", json=payload, headers=api_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data.get("allowed_values", []) == updated_sources
