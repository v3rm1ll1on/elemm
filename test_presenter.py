from elemm_v2.core.models import Landmark
from elemm_v2.core.presenter import ManifestPresenter

tool1 = Landmark(id="test:tool1", description="No params")
tool2 = Landmark(id="test:tool2", description="With return", returns="String response")

presenter = ManifestPresenter()
print(presenter._get_sig(tool1))
print(presenter._get_sig(tool2))
