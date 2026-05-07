import pytest
from elemm_v2.core.presenter import ManifestPresenter
from elemm_v2.core.models import Landmark

def test_presenter_redundancy_filter():
    presenter = ManifestPresenter()
    
    # Tool 1: Redundante Beschreibung (Id ist fast gleich)
    lm1 = Landmark(id="get_user", description="Get user")
    
    # Tool 2: Wertvolle Beschreibung
    lm2 = Landmark(id="get_user", description="Fetches the full user profile including history.")

    md1 = presenter.present_manifest([lm1], full=True)
    md2 = presenter.present_manifest([lm2], full=True)

    # In md1 sollte die Description NICHT auftauchen (Redundanz-Filter)
    assert "Description:" not in md1
    
    # In md2 sollte sie auftauchen
    assert "Description: Fetches the full user profile" in md2

def test_presenter_short_description_filter():
    presenter = ManifestPresenter()
    
    # Zu kurze Beschreibung
    lm = Landmark(id="op", description="Op")
    md = presenter.present_manifest([lm], full=True)
    
    assert "Description:" not in md
