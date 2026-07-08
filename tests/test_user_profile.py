from backend.models.user_profile import UserProfile


def test_user_profile_phase_4_fields_are_optional() -> None:
    profile = UserProfile()

    assert profile.nationality is None
    assert profile.current_country is None
    assert profile.age is None
    assert profile.education is None
    assert profile.profession is None
    assert profile.employment_status is None
    assert profile.intended_canton is None
    assert profile.intended_city is None
    assert profile.purpose_of_stay is None
    assert profile.marital_status is None
    assert profile.children is None
    assert profile.criminal_record is None
    assert profile.current_permit is None
    assert profile.spouse_nationality is None
    assert profile.sponsor_permit is None
    assert profile.relationship is None
    assert profile.driving_licence_country is None
    assert profile.swiss_residence_start_date is None
