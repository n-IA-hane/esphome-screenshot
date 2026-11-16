"""Keep legacy compatibility and actual coordinated MIPI codegen as separate gates."""
from pathlib import Path
import ast
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_real_mipi_job_uses_the_existing_source_authority_and_requires_four_cases():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert all(step.get("with", {}).get("python-version") != "3.14.2"
               for job in workflow["jobs"].values() for step in job["steps"])
    assert "esphome==2026.10.0" in (ROOT / "requirements-dev.txt").read_text()
    job = workflow["jobs"]["mipi-codegen"]
    assert any("373224c141dceadbb67ace263040cbfc802c5968" in step.get("run", "")
               for step in job["steps"])
    checkout = next(step for step in job["steps"]
                    if step.get("with", {}).get("repository") == "n-IA-hane/esphome-intercom")
    assert checkout["with"]["ref"] == "${{ steps.bootstrap.outputs.backend_ref }}"
    assert "/custom_components/" not in checkout["with"]["sparse-checkout"]
    validator = next(step for step in job["steps"] if "requested_refs" in step.get("run", ""))
    assert "scripts/coordinated_sources.py" in validator["run"]
    assert "requested_repositories" in validator["run"]
    execution = next(step for step in job["steps"] if step.get("name") == "Execute all four real provider code-generation cases")
    assert execution["env"]["ESP_SCREENSHOT_MIPI_SOURCE"].endswith("/esphome/components")
    assert "test_mipi_owner_capability_real_schema_codegen" in execution["run"]
    assert "len(cases) == 4" in execution["run"] and 'case.find("skipped")' in execution["run"]
    for step in job["steps"]:
        text = step.get("run", "")
        if "<<'PYCODE'" in text:
            ast.parse(text.split("<<'PYCODE'", 1)[1].split("PYCODE", 1)[0])
