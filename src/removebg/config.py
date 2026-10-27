from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "data" / "outputs"
MODELS = ROOT / "models"
SAM_ID = "facebook/sam2.1-hiera-small"


def prepare_dirs():
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
