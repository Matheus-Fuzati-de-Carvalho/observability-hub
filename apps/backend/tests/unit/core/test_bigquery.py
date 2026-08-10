import pytest
from google.api_core.exceptions import Forbidden, NotFound

from observability_hub.core.bigquery import discover_regions
from observability_hub.core.exceptions import ProjectAccessDeniedError, ProjectNotFoundError


def test_discover_regions_returns_regions_with_data():
    def probe(client, project_id, region):
        return region if region == "US" else None

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == ["US"]


def test_discover_regions_returns_empty_list_for_accessible_empty_project():
    def probe(client, project_id, region):
        return None

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == []


def test_discover_regions_raises_access_denied_when_any_region_forbidden():
    def probe(client, project_id, region):
        if region == "US":
            raise Forbidden("no access")

    with pytest.raises(ProjectAccessDeniedError):
        discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)


def test_discover_regions_raises_not_found_when_all_regions_not_found():
    def probe(client, project_id, region):
        raise NotFound("no project")

    with pytest.raises(ProjectNotFoundError):
        discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)


def test_discover_regions_prefers_found_data_over_errors_in_other_regions():
    def probe(client, project_id, region):
        if region == "US":
            return "US"
        raise NotFound("no data here")

    result = discover_regions("proj", client=object(), regions=["US", "EU"], probe=probe)

    assert result == ["US"]
