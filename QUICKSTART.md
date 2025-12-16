1. install docker
2. ensure you are in root directory of project

3. run this. change the config file to yours
$env:CONFIG_FILE="./config/<your config>"; docker-compose --env-file ./config/.env up
4. if you want run game with 2 config, run this.
$env:CONFIG_FILE="./config/config_opr.yml"; $env:CONFIG_FILE2="./config/config_opr_2.yml"; docker-compose --env-file ./config/.env --profile multi up
5. 

6. use start.ps1, this will export the docker log to docker-logs.
.\start.ps1 -Multi -Config1 "./config/config_opr.yml" -Config2 "./config/config_opr_2.yml"



如何排查：
1. 本地run agent,server
2. docker run server, 本地run agent
3. docker run 