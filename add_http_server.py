import json

config_path = '/app/napcat/config/onebot11_3228649756.json'
with open(config_path) as f:
    cfg = json.load(f)

cfg['network']['httpServers'] = [{
    "enable": True,
    "name": "api",
    "host": "0.0.0.0",
    "port": 6100,
    "enableCors": True,
    "enableWebsocket": False,
    "messagePostFormat": "array",
    "token": "udimc123",
    "debug": False,
}]

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)

print('HTTP Server added on port 6100')
