# Store Monitoring API


## Setup 

Prerequisites
- Python 3.10

1. Create a virtual environment 
```cmd
python3.10 -m venv venv
```
2. Install requirements
```cmd
pip install pip-tools
pip-sync requirements/prod.txt requirements/dev.txt # if in development 
pip-sync requirements/prod.txt # in production 
```
3. Start the server
```cmd
uvicorn api.main:app
```

## Author 
- [Akhil](https://github.com/officialakhil)