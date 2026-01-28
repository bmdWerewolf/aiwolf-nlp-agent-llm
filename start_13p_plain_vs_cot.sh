#!/bin/bash
docker compose --env-file ./config/.env.13p_plain_vs_cot --profile multi up --build
