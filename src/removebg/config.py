import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = Path(tempfile.gettempdir()) / "RemoveBG-Local" / "outputs"
MODELS = ROOT / "models"
SAM_ID = "facebook/sam2.1-hiera-small"


def clear_outputs():
    shutil.rmtree(OUTPUTS, ignore_errors=True)


def prepare_dirs():
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
