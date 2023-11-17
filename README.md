# nifi-poc-parameters

On line 67 in get_nifi_flow.py put in your process group name(TODO is to make this parametrized)

Run nifi instances with registry:
```bash
docker-compose up
```
This will launch 2 NiFi environments with 2 NiFi registries
Accesible at 127.0.0.1:8082, 127.0.0.1:8083

Run:
```bash
./setup_venv.sh
source venv/bin/activate
python get_nifi_flow.py
```
