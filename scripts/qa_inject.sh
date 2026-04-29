#!/usr/bin/env bash
# QA-1 inject helper — wraps curl against /qa/inject.
# Requires uvicorn started with KIN_QA_MODE=1.
#
# Usage:
#   scripts/qa_inject.sh audit '{"event_type":"intake_created","record_ids":["..."],"source_device_id":"tent_a","language":"es"}'
#   scripts/qa_inject.sh structlog '{"event":"whisper.transcribe.start","fields":{"lang":"es"}}'
#
# For convenience, this script also accepts canned shorthand commands
# matching the QA-1 protocol's bullet list.
set -euo pipefail

HOST="${KIN_HOST:-127.0.0.1}"
PORT="${KIN_PORT:-8000}"
URL="http://${HOST}:${PORT}/qa/inject"

# Pre-built UUIDs so audit events can target the same auto-seeded
# records across calls within a QA-1 session.
TENT_A_RID="00000000-0000-0000-0000-00000000000a"
TENT_B_RID="00000000-0000-0000-0000-00000000000b"

post() {
  local kind="$1" payload="$2"
  curl -fsS -X POST "$URL" \
    -H 'Content-Type: application/json' \
    -d "{\"kind\":\"${kind}\",\"payload\":${payload}}"
  echo
}

cmd="${1:-help}"
case "$cmd" in
  audit|structlog)
    post "$cmd" "$2"
    ;;

  # ── QA-1 canned shorthand ────────────────────────────────────────
  qa1-tent-a-init)
    post audit "{\"event_type\":\"intake_created\",\"record_ids\":[\"${TENT_A_RID}\"],\"source_device_id\":\"tent_a\",\"language\":\"es\"}"
    post audit "{\"event_type\":\"field_extracted\",\"record_ids\":[\"${TENT_A_RID}\"],\"source_device_id\":\"tent_a\",\"language\":\"es\",\"details\":{\"field_name\":\"full_name_source_script\",\"value\":\"Carlos\"}}"
    ;;
  qa1-tent-b-init)
    post audit "{\"event_type\":\"intake_created\",\"record_ids\":[\"${TENT_B_RID}\"],\"source_device_id\":\"tent_b\",\"language\":\"ar\"}"
    post audit "{\"event_type\":\"field_extracted\",\"record_ids\":[\"${TENT_B_RID}\"],\"source_device_id\":\"tent_b\",\"language\":\"ar\",\"details\":{\"field_name\":\"full_name_source_script\",\"value\":\"محمد\"}}"
    ;;
  # Pipeline-flow + burst tag source_device_id so the SSE filter
  # correctly routes them to one panel only. Default tent_a.
  qa1-pipeline-flow)
    tent="${2:-tent_a}"
    post structlog "{\"event\":\"whisper.transcribe.start\",\"fields\":{\"lang\":\"es\",\"source_device_id\":\"${tent}\"}}"
    sleep 0.3
    post structlog "{\"event\":\"ollama.translate.invoked\",\"fields\":{\"lang\":\"es\",\"source_device_id\":\"${tent}\"}}"
    sleep 0.3
    post structlog "{\"event\":\"ollama.tool_call.invoked\",\"fields\":{\"tool\":\"extract_intake_fields\",\"source_device_id\":\"${tent}\"}}"
    sleep 0.3
    post structlog "{\"event\":\"ollama.tool_call.returned\",\"fields\":{\"tool\":\"extract_intake_fields\",\"source_device_id\":\"${tent}\"}}"
    sleep 0.3
    post structlog "{\"event\":\"safety_rules.classify\",\"fields\":{\"is_crisis\":false,\"source_device_id\":\"${tent}\"}}"
    ;;
  qa1-burst)
    tent="${2:-tent_a}"
    for i in $(seq 1 20); do
      post structlog "{\"event\":\"qa_burst.event_${i}\",\"fields\":{\"i\":${i},\"source_device_id\":\"${tent}\"}}"
    done
    ;;

  help|*)
    cat <<EOF
qa_inject.sh — QA-1 inject helper

Subcommands:
  audit '<json>'        Inject an audit event (payload is the audit shape)
  structlog '<json>'    Inject a structlog event ({event, fields})

  qa1-tent-a-init               Seed Tent A: intake_created (es) + field_extracted Carlos
  qa1-tent-b-init               Seed Tent B: intake_created (ar) + field_extracted محمد
  qa1-pipeline-flow [tent]      5-event structlog pipeline trace tagged with source_device_id
                                (default tent_a)
  qa1-burst [tent]              20 rapid structlog events tagged with source_device_id
                                (default tent_a)

Env:
  KIN_HOST              Host (default 127.0.0.1)
  KIN_PORT              Port (default 8000)

Server must be started with KIN_QA_MODE=1 .venv/bin/uvicorn ui.server.main:app --app-dir src
EOF
    ;;
esac
