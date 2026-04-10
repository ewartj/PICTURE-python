"""Tests for the YAML app config parser.

Covers:
- Top-level fields (title, description, creator, dataset, img)
- initialCohorts → CohortDefinition parsing
- analysis tabs and methodList parsing
- outputs (interactive / pdf flags)
- R-style TRUE/FALSE normalisation in params
- !datelist custom YAML tag
- all_rdv_names property
- Multiple files via load_app_configs()
- Error cases: missing file, missing title
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from core.config.app_config import AppConfig, load_app_config, load_app_configs

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURES / "sample_app.yaml"
DATELIST_YAML = FIXTURES / "datelist_app.yaml"


# ---------------------------------------------------------------------------
# Top-level fields
# ---------------------------------------------------------------------------


class TestTopLevelFields:
    def test_title(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.title == "Test App"

    def test_description(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert "sample app" in cfg.description.lower()

    def test_creator(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.creator == "test@example.com"

    def test_dataset(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.dataset == "study01"

    def test_img(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.img == "www/images/test.png"

    def test_amount_of_data(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.amount_of_data == "limited"

    def test_offer_cohort_builder(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.offer_cohort_builder is True

    def test_source_path(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.source_path == SAMPLE_YAML

    def test_id_default(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.id == 1

    def test_id_override(self):
        cfg = load_app_config(SAMPLE_YAML, app_id=7)
        assert cfg.id == 7


# ---------------------------------------------------------------------------
# initialCohorts
# ---------------------------------------------------------------------------


class TestInitialCohorts:
    def setup_method(self):
        self.cfg = load_app_config(SAMPLE_YAML)

    def test_two_cohorts(self):
        assert len(self.cfg.initial_cohorts) == 2

    def test_cohort_labels(self):
        labels = [c.label for c in self.cfg.initial_cohorts]
        assert labels == ["Female", "Male"]

    def test_cohort_filter_step_count(self):
        for cohort in self.cfg.initial_cohorts:
            assert len(cohort.config) == 1

    def test_female_filter_fields(self):
        step = self.cfg.initial_cohorts[0].config[0]
        assert step.rdv == "pde"
        assert step.column == "sex_name"
        assert step.query_type == "str_matches"
        assert step.inclusion == "ever"
        assert "Female" in step.val

    def test_val_is_always_list(self):
        """cohort_definition_from_yaml must wrap scalar vals in a list."""
        for cohort in self.cfg.initial_cohorts:
            for step in cohort.config:
                assert isinstance(step.val, list)


# ---------------------------------------------------------------------------
# Analysis tabs and methods
# ---------------------------------------------------------------------------


class TestAnalysis:
    def setup_method(self):
        self.cfg = load_app_config(SAMPLE_YAML)

    def test_tab_count(self):
        assert len(self.cfg.analysis) == 2

    def test_tab_names(self):
        names = [t.tab for t in self.cfg.analysis]
        assert names == ["Demographics", "Diagnoses"]

    def test_demographics_method(self):
        tab = self.cfg.analysis[0]
        assert len(tab.method_list) == 1
        method = tab.method_list[0]
        assert method.fn == "tpl_pde_all"
        assert method.rpkg == "driveanalytics"

    def test_diagnoses_has_one_method(self):
        tab = self.cfg.analysis[1]
        assert len(tab.method_list) == 1

    def test_frequency_method_params(self):
        method = self.cfg.analysis[1].method_list[0]
        assert method.fn == "gen_frequency_analysis"
        assert method.tab_lbl == "Common diagnoses"
        assert method.params["event_col"] == "diag_name"

    def test_rdv_params(self):
        method = self.cfg.analysis[1].method_list[0]
        assert method.rdv_params == {"df_rdv": "df_dia"}

    def test_static_params(self):
        method = self.cfg.analysis[1].method_list[0]
        assert method.static_params == {"event_col": "diag_name"}


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class TestOutputs:
    def test_interactive_true(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.outputs.interactive is True

    def test_pdf_false(self):
        cfg = load_app_config(SAMPLE_YAML)
        assert cfg.outputs.pdf is False


# ---------------------------------------------------------------------------
# all_rdv_names property
# ---------------------------------------------------------------------------


class TestAllRdvNames:
    def test_rdv_names_extracted(self):
        cfg = load_app_config(SAMPLE_YAML)
        # df_pde, df_loc, df_dia → pde, loc, dia
        assert cfg.all_rdv_names == {"pde", "loc", "dia"}


# ---------------------------------------------------------------------------
# !datelist custom tag
# ---------------------------------------------------------------------------


class TestDatelistTag:
    def test_datelist_parsed_as_datetimes(self):
        cfg = load_app_config(DATELIST_YAML)
        step = cfg.initial_cohorts[0].config[0]
        assert len(step.val) == 2
        assert all(isinstance(v, datetime) for v in step.val)

    def test_datelist_values(self):
        cfg = load_app_config(DATELIST_YAML)
        step = cfg.initial_cohorts[0].config[0]
        assert step.val[0].year == 2020
        assert step.val[0].month == 1
        assert step.val[1].month == 12


# ---------------------------------------------------------------------------
# load_app_configs (multiple files)
# ---------------------------------------------------------------------------


class TestLoadAppConfigs:
    def test_ids_are_sequential(self):
        configs = load_app_configs([SAMPLE_YAML, DATELIST_YAML])
        assert [c.id for c in configs] == [1, 2]

    def test_correct_titles(self):
        configs = load_app_configs([SAMPLE_YAML, DATELIST_YAML])
        assert configs[0].title == "Test App"
        assert configs[1].title == "Datelist Test App"

    def test_empty_list(self):
        assert load_app_configs([]) == []


# ---------------------------------------------------------------------------
# Minimal YAML (inline)
# ---------------------------------------------------------------------------


class TestMinimalYaml:
    def test_minimal_valid(self, tmp_path):
        p = tmp_path / "minimal.yaml"
        p.write_text("title: Minimal App\n")
        cfg = load_app_config(p)
        assert cfg.title == "Minimal App"
        assert cfg.initial_cohorts == []
        assert cfg.analysis == []
        assert cfg.outputs.interactive is True
        assert cfg.outputs.pdf is False

    def test_analysis_with_no_methods(self, tmp_path):
        p = tmp_path / "notabs.yaml"
        p.write_text(textwrap.dedent("""\
            title: No Methods
            analysis:
              - tab: Empty Tab
                methodList: []
        """))
        cfg = load_app_config(p)
        assert len(cfg.analysis) == 1
        assert cfg.analysis[0].method_list == []


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_app_config(Path("/nonexistent/path.yaml"))

    def test_missing_title_raises(self, tmp_path):
        p = tmp_path / "notitle.yaml"
        p.write_text("description: No title here\n")
        with pytest.raises(ValueError, match="title"):
            load_app_config(p)

    def test_non_mapping_yaml_raises(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_app_config(p)
