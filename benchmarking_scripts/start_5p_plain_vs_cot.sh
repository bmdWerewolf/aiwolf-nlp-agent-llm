#!/bin/bash
PORT=8082 docker compose -p plain_vs_cot_5p --env-file ./config/.env.5p_plain_vs_cot --profile multi up --build
