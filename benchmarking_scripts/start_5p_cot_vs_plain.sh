#!/bin/bash
PORT=8081 docker compose -p cot_vs_plain_5p --env-file ./config/.env.5p_cot_vs_plain --profile multi up --build
