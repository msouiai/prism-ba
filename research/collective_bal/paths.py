import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parent
GEOMETRY = ROOT.parent/'geometry_agenda'
sys.path.insert(0, str(GEOMETRY))
