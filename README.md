# Store Monitoring API


## Setup 

The easiest way to run this locally is by using [docker-compose](https://docs.docker.com/compose/)

- Clone the repo
```
git clone git@github.com:officialakhil/store_monitoring.git
```
- Change directory to the project
```
cd store_monitoring
```
- Run using docker-compose
```
docker-compose up -d
```
- After everything is up, run a seed script to insert data into postgresql the first time
```
docker exec -it store_monitoring-backend_1 python scripts/seed.py
```

The docker-compose mainly spins up 5 containers:
- Redis ( shared between backend and arq worker )
- Postgresql ( shared between backend and arq worker )
- Backend ( a FastAPI application )
- Arq worker ( a worker node for async redis queue )
- Frontend ( a React app )

Triggering a report generation adds a task into the redis queue which is processed by the worker node as soon as it can. The results are written back to redis ( progress, status etc ) and generated reports are currently saved in a folder locally (should probably move to something like S3 later on)

## Test it 
You can visit http://localhost:3000/ for a simple UI for playing with the report generation api. Or you can use curl
```
curl -X POST http://localhost:8000/api/v1/reports/trigger_report | jq
```
Sample output:
```json
{
  "message": "Report triggered",
  "task_id": "7995cd0aafa945c29521e8a27a2859fa"
}
```

Check status of the task
```
curl -X GET http://localhost:8000/api/v1/reports/get_report?report_id=7995cd0aafa945c29521e8a27a2859fa | jq 
```
Sample output:
```json
{
  "message": "Report in progress",
  "report_id": "7995cd0aafa945c29521e8a27a2859fa",
  "stores_processed": 5467,
  "total_stores": 14092
}
```
The same endpoint gives a `text/csv` instead of `application/json` if report generation is complete. 

## Author 
- [Akhil](https://github.com/officialakhil)