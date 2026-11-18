from app.config import Settings


def test_empty_default_ids_are_treated_as_unset():
    settings = Settings(
        default_domain_id="",
        default_group_id="",
        default_source_id="",
    )

    assert settings.default_domain_id is None
    assert settings.default_group_id is None
    assert settings.default_source_id is None
