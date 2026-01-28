#!/bin/bash
docker compose --env-file ./config/.env.13p_cot_vs_plain --profile multi up --build
