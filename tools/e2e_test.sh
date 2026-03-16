#!/bin/bash
set -e

API="http://localhost:8000/api/v1"
SAMPLE="samples/sample_contracts/Sample Contract.pdf"

echo "Health check..."
curl -sS $API/health | jq .

echo "Uploading and building index..."
resp=$(curl -s -F "file=@${SAMPLE}" $API/index/build)
echo "Response: $resp"
job_id=$(echo $resp | jq -r '.job_id')

if [ -z "$job_id" ] || [ "$job_id" = "null" ]; then
  echo "No job_id returned; aborting."
  exit 1
fi

echo "Polling job $job_id..."
for i in {1..60}; do
  status=$(curl -s $API/index/status/$job_id)
  echo "$status" | jq .
  state=$(echo $status | jq -r '.state')
  if [ "$state" = "done" ]; then
    echo "Index build complete."
    break
  fi
  if [ "$state" = "error" ]; then
    echo "Index build failed."
    exit 1
  fi
  sleep 2
done

echo "Running a sample search..."
curl -s "$API/search?q=rotate%20break-glass%20credentials%2090%20days&k=5" | jq .
