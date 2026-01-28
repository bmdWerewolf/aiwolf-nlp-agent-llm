#!/bin/bash
PORT=8083 docker compose -p cot_vs_plain_13p --env-file ./config/.env.13p_cot_vs_plain --profile multi up --build
