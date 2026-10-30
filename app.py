"""PDi Control of Work standalone client demonstration."""
from pathlib import Path
BASE=Path(__file__).parent
exec(compile((BASE/"core_app.py").read_text(),"core_app.py","exec"),{"__name__":"__main__","__file__":str(BASE/"core_app.py")})
