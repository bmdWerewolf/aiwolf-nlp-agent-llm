#!/bin/bash
docker compose --env-file ./config/.env.5p_plain_vs_cot --profile multi up --build
