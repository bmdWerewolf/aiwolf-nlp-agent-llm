#!/bin/bash
PORT=8084 docker compose -p plain_vs_cot_13p --env-file ./config/.env.13p_plain_vs_cot --profile multi up --build
