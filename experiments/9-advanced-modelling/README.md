# Setup

SageMath needs to be installed system-wide (as it is more than just a PIP package) and a based on the system-wide Python a local virtual environment needs to be created!

```bash
sudo pacman -S python python-pip sagemath
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py 
```
