here is a sop when you encountered problems. and remember change all the specific files to your own version.
# run all locally
./server/aiwolf-nlp-server-windows-amd64.exe -c ./server/default_5.yml
python src/main.py -c ./config/config_opr_local.yml
# run all with 2 configs locally
 ./server/aiwolf-nlp-server-windows-amd64.exe -c ./server/default_5_2Teams.yml
python src/main.py -c ./config/config_opr_local_multi_1.yml ./config/config_opr_local_multi_2.yml

# verify that the server can run correctly with multi configs
docker build -t aiwolf-server ./server
docker run -d --name aiwolf-server `
  -p 8080:8080 `
  -v ${PWD}/server:/app/config `
  -v ${PWD}/server/logs:/app/log `
  aiwolf-server
python src/main.py -c ./config/config_opr_local_multi_1.yml ./config/config_opr_local_multi_2.yml

## verify that you can run all using docker with multi configs
# clean
docker rm -f aiwolf-server aiwolf-agent 2>$null

# run server
docker run -d --name aiwolf-server `
  -p 8080:8080 `
  -v ${PWD}/server:/app/config `
  -v ${PWD}/server/logs:/app/log `
  aiwolf-server

Start-Sleep -Seconds 3

# run agent 
docker run -d --name aiwolf-agent `
  --env-file ${PWD}/config/.env `
  -v ${PWD}/config:/app/config `
  -v ${PWD}/log:/app/log `
  --add-host=host.docker.internal:host-gateway `
  aiwolf-agent `
  uv run python src/main.py -c ./config/config_opr_multi_1.yml ./config/config_opr_multi_2.yml

# view logs
docker logs -f aiwolf-agent

## verify that you can use docker-compose to run all 
# single mode
docker rm -f aiwolf-server aiwolf-agent aiwolf-agent-multi 2>$null
docker-compose --env-file ./config/.env --profile single up

docker-compose --env-file ./config/.env --profile single down
# multiple mode
# set server use 2 Teams configs
$env:SERVER_CONFIG = "default_5_2Teams.yml"
docker-compose --env-file ./config/.env --profile multi up

# run while preserving logs
docker-compose --env-file ./config/.env --profile multi up 2>&1 | Tee-Object -FilePath ./docker-logs/$(Get-Date -Format "yyyyMMdd_HHmmss").log