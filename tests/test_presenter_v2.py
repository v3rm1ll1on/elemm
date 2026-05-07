import pytest
from elemm.core.presenter import ManifestPresenter
from elemm.core.models import Landmark

def test_presenter_redundancy_filter():
    presenter = ManifestPresenter()
    
    # Tool 1: Redundante Beschreibung (Id ist fast gleich)
    lm1 = Landmark(id="get_user", description="Get user", handler=lambda: None)
    
    # Tool 2: Wertvolle Beschreibung
    lm2 = Landmark(id="get_user", description="Fetches the full user profile including history.", handler=lambda: None)

    md1 = presenter.present_manifest([lm1], hide_json=False)
    md2 = presenter.present_manifest([lm2], hide_json=False)

    # In md1 sollte die Description aktuell noch auftauchen (Filter noch nicht aktiv)
    assert "Description: Get user" in md1
    
    # In md2 sollte sie ebenfalls auftauchen
    assert "Description: Fetches the full user profile" in md2

def test_presenter_short_description_filter():
    presenter = ManifestPresenter()
    
    # Zu kurze Beschreibung
    lm = Landmark(id="op", description="Op", handler=lambda: None)
    md = presenter.present_manifest([lm], hide_json=False)
    
    # In v2 unhardened tauchen auch kurze Beschreibungen auf
    assert "Description: Op" in md
